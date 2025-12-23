"""
Service de telechargement et mise a jour des fichiers BDPM.

Fonctionnalites:
- Telechargement des fichiers BDPM depuis le site officiel
- Comparaison par hash SHA256 pour eviter les telechargements inutiles
- Integration en base avec detection des nouveaux/absents CIP
- Verification automatique toutes les 24h + bouton manuel
"""
import hashlib
import codecs
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import BdpmEquivalence, BdpmFileStatus

logger = logging.getLogger(__name__)

# Configuration
BDPM_BASE_URL = "https://base-donnees-publique.medicaments.gouv.fr/index.php/download/file"
BDPM_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "bdpm"
CHECK_INTERVAL_HOURS = 24

# Fichiers BDPM a telecharger
BDPM_FILES = {
    "CIS_bdpm.txt": "Fichier des specialites (denominations, statut)",
    "CIS_CIP_bdpm.txt": "Fichier des presentations (CIP13, prix)",
    "CIS_GENER_bdpm.txt": "Fichier des groupes generiques",
}


@dataclass
class BdpmUpdateResult:
    """Resultat d'une mise a jour BDPM."""
    filename: str
    downloaded: bool
    hash_changed: bool
    new_records: int
    removed_records: int
    total_records: int
    error: Optional[str] = None


def ensure_data_dir():
    """S'assure que le dossier de donnees existe."""
    BDPM_DATA_PATH.mkdir(parents=True, exist_ok=True)


def compute_file_hash(filepath: Path) -> Optional[str]:
    """Calcule le hash SHA256 d'un fichier."""
    if not filepath.exists():
        return None

    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


async def download_file(filename: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Telecharge un fichier BDPM.

    Returns:
        Tuple (success, hash, size)
    """
    url = f"{BDPM_BASE_URL}/{filename}"
    filepath = BDPM_DATA_PATH / filename

    ensure_data_dir()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            content = response.content

            # Sauvegarder le fichier
            with open(filepath, "wb") as f:
                f.write(content)

            # Calculer le hash
            file_hash = hashlib.sha256(content).hexdigest()
            file_size = len(content)

            logger.info(f"Telecharge {filename}: {file_size} octets, hash={file_hash[:16]}...")
            return True, file_hash, file_size

    except Exception as e:
        logger.error(f"Erreur telechargement {filename}: {e}")
        return False, None, None


def get_file_status(db: Session, filename: str) -> Optional[BdpmFileStatus]:
    """Recupere le statut d'un fichier BDPM."""
    return db.query(BdpmFileStatus).filter(BdpmFileStatus.filename == filename).first()


def update_file_status(
    db: Session,
    filename: str,
    file_hash: Optional[str] = None,
    file_size: Optional[int] = None,
    last_checked: Optional[datetime] = None,
    last_downloaded: Optional[datetime] = None,
    last_integrated: Optional[datetime] = None,
    records_count: Optional[int] = None,
    new_records: Optional[int] = None,
    removed_records: Optional[int] = None,
) -> BdpmFileStatus:
    """Met a jour ou cree le statut d'un fichier BDPM."""
    status = get_file_status(db, filename)

    if not status:
        status = BdpmFileStatus(
            filename=filename,
            file_url=f"{BDPM_BASE_URL}/{filename}",
        )
        db.add(status)

    if file_hash is not None:
        status.file_hash = file_hash
    if file_size is not None:
        status.file_size = file_size
    if last_checked is not None:
        status.last_checked = last_checked
    if last_downloaded is not None:
        status.last_downloaded = last_downloaded
    if last_integrated is not None:
        status.last_integrated = last_integrated
    if records_count is not None:
        status.records_count = records_count
    if new_records is not None:
        status.new_records = new_records
    if removed_records is not None:
        status.removed_records = removed_records

    db.commit()
    db.refresh(status)
    return status


def needs_check(db: Session) -> bool:
    """Verifie si une verification BDPM est necessaire (> 24h depuis dernier check)."""
    # Verifier le fichier principal CIS_GENER
    status = get_file_status(db, "CIS_GENER_bdpm.txt")

    if not status or not status.last_checked:
        return True

    elapsed = datetime.utcnow() - status.last_checked.replace(tzinfo=None)
    return elapsed > timedelta(hours=CHECK_INTERVAL_HOURS)


def get_bdpm_status(db: Session) -> Dict:
    """Retourne le statut global BDPM pour l'affichage."""
    statuses = db.query(BdpmFileStatus).all()

    if not statuses:
        return {
            "status": "unknown",
            "message": "BDPM jamais verifie",
            "last_checked": None,
            "last_updated": None,
            "files": [],
        }

    # Trouver les dates les plus recentes
    last_checked = max((s.last_checked for s in statuses if s.last_checked), default=None)
    last_downloaded = max((s.last_downloaded for s in statuses if s.last_downloaded), default=None)

    # Determiner le statut
    if last_checked:
        elapsed = datetime.utcnow() - last_checked.replace(tzinfo=None)
        if elapsed < timedelta(hours=24):
            status = "ok"
            message = f"BDPM verifie le {last_checked.strftime('%d/%m/%Y %H:%M')}"
        elif elapsed < timedelta(days=7):
            status = "warning"
            message = f"BDPM verifie il y a {elapsed.days} jours"
        else:
            status = "outdated"
            message = f"BDPM non verifie depuis {elapsed.days} jours"
    else:
        status = "unknown"
        message = "BDPM jamais verifie"

    return {
        "status": status,
        "message": message,
        "last_checked": last_checked.isoformat() if last_checked else None,
        "last_updated": last_downloaded.isoformat() if last_downloaded else None,
        "files": [
            {
                "filename": s.filename,
                "last_checked": s.last_checked.isoformat() if s.last_checked else None,
                "last_downloaded": s.last_downloaded.isoformat() if s.last_downloaded else None,
                "records_count": s.records_count,
                "new_records": s.new_records,
                "removed_records": s.removed_records,
            }
            for s in statuses
        ],
    }


def parse_cis_gener(filepath: Path) -> Dict[str, Dict]:
    """Parse CIS_GENER_bdpm.txt et retourne un dict cip13 -> info."""
    # 1. Parser CIS_bdpm.txt pour avoir CIS -> denomination
    cis_filepath = filepath.parent / "CIS_bdpm.txt"
    cis_to_denomination: Dict[str, str] = {}
    if cis_filepath.exists():
        with codecs.open(cis_filepath, 'r', encoding='latin-1') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    cis = parts[0]
                    denomination = parts[1]
                    if cis:
                        cis_to_denomination[cis] = denomination

    # 2. Parser CIS_CIP pour avoir les CIP13 et les prix
    cip_filepath = filepath.parent / "CIS_CIP_bdpm.txt"
    cis_to_cips: Dict[str, List[Dict]] = {}
    if cip_filepath.exists():
        with codecs.open(cip_filepath, 'r', encoding='latin-1') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    cis = parts[0]
                    cip13 = parts[6]
                    # Prix PFHT en colonne 10 (index 9)
                    pfht = None
                    if len(parts) >= 10 and parts[9].strip():
                        try:
                            pfht = float(parts[9].replace(',', '.'))
                        except ValueError:
                            pass

                    if cis and cip13 and len(cip13) == 13 and cip13.isdigit():
                        if cis not in cis_to_cips:
                            cis_to_cips[cis] = []
                        cis_to_cips[cis].append({"cip13": cip13, "pfht": pfht})

    # 3. Parser CIS_GENER et collecter les princeps par groupe
    groupe_to_princeps: Dict[int, str] = {}  # groupe_id -> denomination du princeps
    result = {}

    with codecs.open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                groupe_id = parts[0]
                libelle = parts[1]
                cis = parts[2]
                type_gen = parts[3]

                groupe_id_int = int(groupe_id) if groupe_id.isdigit() else None
                type_gen_int = int(type_gen) if type_gen.isdigit() else None
                denomination = cis_to_denomination.get(cis, "")

                # Si c'est un princeps (type 0), enregistrer sa denomination
                if type_gen_int == 0 and groupe_id_int and denomination:
                    groupe_to_princeps[groupe_id_int] = denomination

                # Trouver les CIP13 et prix pour ce CIS
                cip_infos = cis_to_cips.get(cis, [])
                for cip_info in cip_infos:
                    cip13 = cip_info["cip13"]
                    pfht = cip_info["pfht"]
                    result[cip13] = {
                        "cis": cis,
                        "groupe_generique_id": groupe_id_int,
                        "libelle_groupe": libelle,
                        "type_generique": type_gen_int,
                        "pfht": pfht,
                        "denomination": denomination,
                    }

    # 4. Ajouter le princeps_denomination a chaque entree
    for cip13, data in result.items():
        groupe_id = data.get("groupe_generique_id")
        if groupe_id and groupe_id in groupe_to_princeps:
            data["princeps_denomination"] = groupe_to_princeps[groupe_id]
        else:
            data["princeps_denomination"] = None

    return result


async def check_and_update_bdpm(db: Session, force: bool = False) -> Dict:
    """
    Verifie et met a jour les fichiers BDPM si necessaire.

    Args:
        db: Session SQLAlchemy
        force: Si True, force le telechargement meme si le hash n'a pas change

    Returns:
        Dict avec les resultats de la mise a jour
    """
    results = {
        "checked": True,
        "files_updated": 0,
        "new_cips": 0,
        "removed_cips": 0,
        "details": [],
    }

    ensure_data_dir()
    now = datetime.utcnow()

    for filename, description in BDPM_FILES.items():
        filepath = BDPM_DATA_PATH / filename
        status = get_file_status(db, filename)
        old_hash = status.file_hash if status else None

        # Telecharger le fichier
        success, new_hash, file_size = await download_file(filename)

        if not success:
            results["details"].append({
                "filename": filename,
                "status": "error",
                "message": "Echec du telechargement",
            })
            continue

        # Mettre a jour le statut
        hash_changed = old_hash != new_hash

        update_file_status(
            db,
            filename=filename,
            file_hash=new_hash,
            file_size=file_size,
            last_checked=now,
            last_downloaded=now if hash_changed or force else None,
        )

        if hash_changed:
            results["files_updated"] += 1

        results["details"].append({
            "filename": filename,
            "status": "updated" if hash_changed else "unchanged",
            "hash_changed": hash_changed,
        })

    # Si CIS_GENER a change, mettre a jour la base
    gener_status = get_file_status(db, "CIS_GENER_bdpm.txt")
    if gener_status and results["files_updated"] > 0:
        integration_result = integrate_bdpm_to_database(db)
        results["new_cips"] = integration_result["new_cips"]
        results["removed_cips"] = integration_result["removed_cips"]

        update_file_status(
            db,
            filename="CIS_GENER_bdpm.txt",
            last_integrated=now,
            records_count=integration_result["total_cips"],
            new_records=integration_result["new_cips"],
            removed_records=integration_result["removed_cips"],
        )

    return results


def integrate_bdpm_to_database(db: Session) -> Dict:
    """
    Integre les donnees BDPM dans la table bdpm_equivalences.

    - Nouveaux CIP -> INSERT
    - CIP modifies -> UPDATE
    - CIP absents -> Marquer absent_bdpm=True (PAS de suppression)

    Returns:
        Dict avec les stats d'integration
    """
    filepath = BDPM_DATA_PATH / "CIS_GENER_bdpm.txt"

    if not filepath.exists():
        return {"error": "Fichier CIS_GENER_bdpm.txt non trouve"}

    # Parser le fichier
    bdpm_data = parse_cis_gener(filepath)
    bdpm_cips = set(bdpm_data.keys())

    # CIP existants en base
    existing_cips = set(
        r[0] for r in db.query(BdpmEquivalence.cip13).all()
    )

    # Calculer les differences
    new_cips = bdpm_cips - existing_cips
    removed_cips = existing_cips - bdpm_cips

    stats = {
        "total_cips": len(bdpm_cips),
        "new_cips": len(new_cips),
        "removed_cips": len(removed_cips),
        "updated_cips": 0,
    }

    # Ajouter les nouveaux CIP
    for cip13 in new_cips:
        data = bdpm_data[cip13]
        record = BdpmEquivalence(
            cip13=cip13,
            cis=data["cis"],
            groupe_generique_id=data["groupe_generique_id"],
            libelle_groupe=data["libelle_groupe"],
            type_generique=data["type_generique"],
            pfht=data.get("pfht"),
            denomination=data.get("denomination"),
            princeps_denomination=data.get("princeps_denomination"),
            absent_bdpm=False,
        )
        db.add(record)

    # Mettre a jour les CIP existants (prix, denomination, princeps)
    existing_to_update = bdpm_cips & existing_cips
    for cip13 in existing_to_update:
        data = bdpm_data[cip13]
        update_fields = {}
        if data.get("pfht") is not None:
            update_fields["pfht"] = data["pfht"]
        if data.get("denomination"):
            update_fields["denomination"] = data["denomination"]
        if data.get("princeps_denomination"):
            update_fields["princeps_denomination"] = data["princeps_denomination"]

        if update_fields:
            db.query(BdpmEquivalence).filter(
                BdpmEquivalence.cip13 == cip13
            ).update(update_fields, synchronize_session=False)
            stats["updated_cips"] += 1

    # Marquer les CIP absents (PAS de suppression)
    if removed_cips:
        db.query(BdpmEquivalence).filter(
            BdpmEquivalence.cip13.in_(removed_cips)
        ).update({BdpmEquivalence.absent_bdpm: True}, synchronize_session=False)

    # Remettre absent_bdpm=False pour les CIP presents
    if bdpm_cips:
        db.query(BdpmEquivalence).filter(
            BdpmEquivalence.cip13.in_(bdpm_cips),
            BdpmEquivalence.absent_bdpm == True
        ).update({BdpmEquivalence.absent_bdpm: False}, synchronize_session=False)

    db.commit()

    logger.info(f"Integration BDPM: {stats}")
    return stats


def get_absent_cips(db: Session) -> List[Dict]:
    """Retourne la liste des CIP marques comme absents de la BDPM."""
    records = db.query(BdpmEquivalence).filter(
        BdpmEquivalence.absent_bdpm == True
    ).all()

    return [
        {
            "cip13": r.cip13,
            "cis": r.cis,
            "libelle_groupe": r.libelle_groupe,
            "type_generique": r.type_generique,
        }
        for r in records
    ]


def delete_absent_cips(db: Session, cip13_list: List[str]) -> int:
    """Supprime definitivement les CIP specifies."""
    deleted = db.query(BdpmEquivalence).filter(
        BdpmEquivalence.cip13.in_(cip13_list)
    ).delete(synchronize_session=False)
    db.commit()
    return deleted
