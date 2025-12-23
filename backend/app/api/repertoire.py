"""
API Repertoire Generique Global.

Endpoints pour:
- Consultation du repertoire des generiques BDPM
- Rapprochement ventes / repertoire
- Gestion des mises a jour BDPM
- Memoire de matching
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import shutil
from pathlib import Path

from app.db.database import get_db
from app.models import BdpmEquivalence, MesVentes, MatchingMemory, BdpmFileStatus
from app.services import bdpm_downloader, matching_memory
from app.services.intelligent_matching import MoleculeExtractor
from rapidfuzz import fuzz, process
import re

router = APIRouter(prefix="/repertoire", tags=["repertoire"])


# =============================================================================
# UTILS FUZZY MATCHING
# =============================================================================

def normalize_libelle(text: str) -> str:
    """Normalise un libelle pour comparaison fuzzy."""
    if not text:
        return ""
    # Minuscules
    text = text.lower()
    # Garder seulement alphanumeriques et espaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Normaliser espaces
    text = ' '.join(text.split())
    return text


def extract_molecule_dosage(designation: str) -> tuple:
    """Extrait molecule et dosage depuis une designation."""
    if not designation:
        return "", ""

    text = designation.upper()

    # Pattern pour dosage: nombre suivi de mg, g, ml, etc.
    dosage_match = re.search(r'(\d+[\d,\.]*)\s*(MG|G|ML|%|MCG|UI)', text)
    dosage = f"{dosage_match.group(1)}{dosage_match.group(2)}" if dosage_match else ""

    # Molecule = premier mot significatif (avant le dosage ou le labo)
    # Nettoyer le texte
    molecule = text.split()[0] if text.split() else ""

    # Si c'est un nom compose (ex: FLUTI/SALMETEROL), garder entier
    if '/' in text.split()[0] if text.split() else False:
        molecule = text.split()[0]

    return molecule, dosage


def extract_molecule_candidates(text: str) -> list:
    """
    Extrait les candidats molecules d'une designation (premiers mots alphabetiques).

    Exemples:
    - "AMLODIPINE 5MG BGR" → ["AMLODIPINE"]
    - "FLUTI/SALMETEROL 250/25 ZTV" → ["FLUTI", "SALMETEROL"]
    - "BIMATOPROST 0,1MG/ML BGR" → ["BIMATOPROST"]

    Retourne une liste (pas un set) pour garder l'ordre.
    """
    if not text:
        return []

    # Normaliser: majuscules, remplacer "/" par espace
    text = text.upper().replace('/', ' ')

    # Liste minimale de mots a ignorer (labos courants)
    ignore_labos = {
        'BGR', 'BIOGARAN', 'VIATRIS', 'MYLAN', 'TEVA', 'SANDOZ', 'EG', 'ARROW',
        'ZENTIVA', 'CRISTERS', 'ACCORD', 'ZYDUS', 'ZTV', 'LP',
    }

    molecules = []
    words = text.split()

    for word in words:
        # Ignorer les labos
        if word in ignore_labos:
            continue
        # Ignorer les chiffres et dosages
        if re.match(r'^[\d,\.]+', word):
            continue
        # Ignorer les mots trop courts
        if len(word) < 4:
            continue
        # Garder uniquement les mots alphabetiques
        if re.match(r'^[A-Z]+$', word):
            molecules.append(word)
            # Limiter a 3 molecules max (les premiers mots)
            if len(molecules) >= 3:
                break

    return molecules


def libelle_contains_molecules(libelle: str, molecules: list, threshold: int = 80) -> bool:
    """
    Verifie si un libelle BDPM contient TOUTES les molecules (avec fuzzy matching).

    Gere les abbreviations: "FLUTI" sera trouve dans "FLUTICASONE".
    """
    if not libelle or not molecules:
        return False

    libelle_upper = libelle.upper()

    for mol in molecules:
        # Essayer d'abord une recherche exacte (substring)
        if mol in libelle_upper:
            continue

        # Sinon, chercher avec fuzzy partial matching
        # Extraire les mots du libelle et chercher un match
        libelle_words = re.findall(r'[A-Z]{4,}', libelle_upper)
        found = False
        for lw in libelle_words:
            if fuzz.partial_ratio(mol, lw) >= threshold:
                found = True
                break

        if not found:
            return False

    return True


def count_molecule_matches(libelle: str, molecules: list) -> int:
    """
    Compte combien de molecules sont presentes dans le libelle.
    Utilise pour filtrer les groupes avec trop de molecules supplementaires.
    """
    if not libelle:
        return 0

    libelle_upper = libelle.upper()
    count = 0
    for mol in molecules:
        if mol in libelle_upper:
            count += 1
        else:
            # Fuzzy check
            libelle_words = re.findall(r'[A-Z]{4,}', libelle_upper)
            for lw in libelle_words:
                if fuzz.partial_ratio(mol, lw) >= 80:
                    count += 1
                    break
    return count


def find_fuzzy_match(designation: str, bdpm_by_libelle: dict, threshold: int = 70) -> Optional[tuple]:
    """
    Trouve un match fuzzy intelligent dans le repertoire BDPM.

    Strategie:
    1. Extraire les molecules candidates de la designation
    2. Chercher les groupes BDPM qui contiennent TOUTES ces molecules
    3. Parmi les candidats, scorer sur le libelle complet

    Cela permet de matcher "FLUTI/SALMETEROL" avec "FLUTICASONE + SALMETEROL".
    """
    if not designation or not bdpm_by_libelle:
        return None

    # Extraire les molecules candidates
    molecules = extract_molecule_candidates(designation)

    # Si on a trouve des molecules, chercher les groupes qui les contiennent
    candidats = {}
    if molecules:
        for key, bdpm in bdpm_by_libelle.items():
            libelle = bdpm.libelle_groupe or ""
            if libelle_contains_molecules(libelle, molecules):
                candidats[key] = bdpm

    # Si pas de candidats avec recherche par molecules, fallback sur tous
    if not candidats:
        candidats = bdpm_by_libelle

    # Scorer sur le libelle complet parmi les candidats
    normalized = normalize_libelle(designation)
    result = process.extractOne(
        normalized,
        list(candidats.keys()),
        scorer=fuzz.token_set_ratio,
        score_cutoff=threshold
    )

    if result:
        matched_key, score, _ = result
        return candidats[matched_key], score

    return None


# =============================================================================
# SCHEMAS
# =============================================================================

class RepertoireItem(BaseModel):
    cip13: str
    cis: Optional[str]
    groupe_generique_id: Optional[int]
    libelle_groupe: Optional[str]
    type_generique: Optional[int]  # 0=princeps, 1=generique
    pfht: Optional[float]
    denomination: Optional[str]  # Nom complet du medicament
    princeps_denomination: Optional[str]  # Nom du princeps du groupe
    absent_bdpm: bool = False
    match_origin: Optional[str] = None  # 'bdpm', 'fuzzy'

    class Config:
        from_attributes = True


class RepertoireStats(BaseModel):
    total_cips: int
    total_groupes: int
    princeps: int
    generiques: int
    avec_prix: int
    sans_prix: int
    absents: int


class BdpmStatus(BaseModel):
    status: str  # 'ok', 'warning', 'outdated', 'unknown'
    message: str
    last_checked: Optional[str]
    last_updated: Optional[str]
    files: List[dict]


class RapprochementRequest(BaseModel):
    import_id: Optional[int] = None  # Si None, toutes les ventes


class RapprochementResultItem(BaseModel):
    vente_id: int
    cip13: Optional[str]
    designation: str
    quantite: int
    montant_ht: float
    status: str  # 'valide', 'a_supprimer', 'a_rattacher'
    pfht: Optional[float] = None  # Prix fabricant HT
    raison_suppression: Optional[str] = None  # 'princeps', 'cip_non_trouve', 'sans_prix'
    groupe_generique_id: Optional[int] = None
    type_generique: Optional[int] = None  # 0=princeps, 1=generique
    match_origin: Optional[str] = None  # 'exact', 'fuzzy', None


class GroupeMembre(BaseModel):
    """Un membre d'un groupe generique."""
    cip13: str
    denomination: Optional[str]
    type_generique: Optional[int]  # 0=princeps, 1=generique
    pfht: Optional[float]


class PropositionRattachement(BaseModel):
    """Proposition de rattachement fuzzy pour validation utilisateur."""
    vente_id: int
    cip13: Optional[str]
    designation: str
    quantite: int
    montant_ht: float
    # Groupe propose
    groupe_generique_id: int
    libelle_groupe: str
    fuzzy_score: float
    # Tous les membres du groupe
    membres_groupe: List[GroupeMembre]
    # Prix propose (du groupe)
    pfht_propose: Optional[float] = None


class RapprochementResult(BaseModel):
    valides: List[RapprochementResultItem]  # Generiques avec prix
    a_supprimer: List[RapprochementResultItem]  # Princeps, non trouves, sans prix
    propositions_rattachement: List[PropositionRattachement]  # Fuzzy matches a valider
    stats: dict


class ValidationRequest(BaseModel):
    vente_ids: List[int]
    action: str  # 'validate_match', 'delete'


class RattachementItem(BaseModel):
    """Item de rattachement a valider."""
    vente_id: int
    cip13: str
    groupe_generique_id: int


class RattachementRequest(BaseModel):
    """Request pour valider des rattachements fuzzy."""
    rattachements: List[RattachementItem]


class MemoryStats(BaseModel):
    total_cips: int
    total_groupes: int
    validated: int
    pending_validation: int


# =============================================================================
# ENDPOINTS REPERTOIRE
# =============================================================================

@router.get("/", response_model=List[RepertoireItem])
def get_repertoire(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    groupe_id: Optional[int] = None,
    type_generique: Optional[int] = None,
    has_price: Optional[bool] = None,
    only_with_groupe: bool = True,
    sort_by: str = "denomination",
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Liste le repertoire des generiques avec filtres et tri."""
    query = db.query(BdpmEquivalence)

    # Filtrer par defaut pour n'avoir que les medicaments avec groupe generique
    if only_with_groupe:
        query = query.filter(BdpmEquivalence.groupe_generique_id.isnot(None))

    if search:
        query = query.filter(
            or_(
                BdpmEquivalence.cip13.ilike(f"%{search}%"),
                BdpmEquivalence.libelle_groupe.ilike(f"%{search}%"),
                BdpmEquivalence.denomination.ilike(f"%{search}%"),
            )
        )

    if groupe_id:
        query = query.filter(BdpmEquivalence.groupe_generique_id == groupe_id)

    if type_generique is not None:
        query = query.filter(BdpmEquivalence.type_generique == type_generique)

    if has_price is not None:
        if has_price:
            query = query.filter(BdpmEquivalence.pfht.isnot(None))
        else:
            query = query.filter(BdpmEquivalence.pfht.is_(None))

    # Exclure les absents par defaut
    query = query.filter(BdpmEquivalence.absent_bdpm == False)

    # Tri dynamique
    sort_column = getattr(BdpmEquivalence, sort_by, BdpmEquivalence.denomination)
    if sort_order == "desc":
        sort_column = sort_column.desc()

    return query.order_by(sort_column).offset(skip).limit(limit).all()


@router.get("/stats", response_model=RepertoireStats)
def get_repertoire_stats(only_with_groupe: bool = True, db: Session = Depends(get_db)):
    """Statistiques du repertoire."""
    base_filter = [BdpmEquivalence.absent_bdpm == False]

    # Si only_with_groupe, ne compter que les medicaments avec groupe generique
    if only_with_groupe:
        base_filter.append(BdpmEquivalence.groupe_generique_id.isnot(None))

    total = db.query(func.count(BdpmEquivalence.cip13)).filter(
        *base_filter
    ).scalar() or 0

    total_groupes = db.query(func.count(func.distinct(BdpmEquivalence.groupe_generique_id))).filter(
        BdpmEquivalence.groupe_generique_id.isnot(None),
        BdpmEquivalence.absent_bdpm == False
    ).scalar() or 0

    princeps = db.query(func.count(BdpmEquivalence.cip13)).filter(
        BdpmEquivalence.type_generique == 0,
        BdpmEquivalence.absent_bdpm == False
    ).scalar() or 0

    generiques = db.query(func.count(BdpmEquivalence.cip13)).filter(
        BdpmEquivalence.type_generique == 1,
        BdpmEquivalence.absent_bdpm == False
    ).scalar() or 0

    avec_prix = db.query(func.count(BdpmEquivalence.cip13)).filter(
        BdpmEquivalence.pfht.isnot(None),
        *base_filter
    ).scalar() or 0

    sans_prix = db.query(func.count(BdpmEquivalence.cip13)).filter(
        BdpmEquivalence.pfht.is_(None),
        *base_filter
    ).scalar() or 0

    absents = db.query(func.count(BdpmEquivalence.cip13)).filter(
        BdpmEquivalence.absent_bdpm == True
    ).scalar() or 0

    return RepertoireStats(
        total_cips=total,
        total_groupes=total_groupes,
        princeps=princeps,
        generiques=generiques,
        avec_prix=avec_prix,
        sans_prix=sans_prix,
        absents=absents,
    )


@router.get("/groupes")
def get_groupes_generiques(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Liste les groupes generiques avec leur nombre de CIP."""
    query = db.query(
        BdpmEquivalence.groupe_generique_id,
        BdpmEquivalence.libelle_groupe,
        func.count(BdpmEquivalence.cip13).label("nb_cips"),
        func.sum(func.cast(BdpmEquivalence.type_generique == 0, db.bind.dialect.name == 'postgresql' and 'INTEGER' or 'INT')).label("nb_princeps"),
    ).filter(
        BdpmEquivalence.groupe_generique_id.isnot(None),
        BdpmEquivalence.absent_bdpm == False
    ).group_by(
        BdpmEquivalence.groupe_generique_id,
        BdpmEquivalence.libelle_groupe
    )

    if search:
        query = query.filter(BdpmEquivalence.libelle_groupe.ilike(f"%{search}%"))

    results = query.order_by(BdpmEquivalence.libelle_groupe).offset(skip).limit(limit).all()

    return [
        {
            "groupe_generique_id": r[0],
            "libelle_groupe": r[1],
            "nb_cips": r[2],
            "nb_princeps": r[3] or 0,
        }
        for r in results
    ]


# =============================================================================
# ENDPOINTS BDPM STATUS
# =============================================================================

@router.get("/bdpm/status", response_model=BdpmStatus)
def get_bdpm_status(db: Session = Depends(get_db)):
    """Retourne le statut des fichiers BDPM."""
    return bdpm_downloader.get_bdpm_status(db)


@router.post("/bdpm/check")
async def check_bdpm_updates(
    force: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Verifie et telecharge les mises a jour BDPM si necessaire."""
    result = await bdpm_downloader.check_and_update_bdpm(db, force=force)
    return result


@router.get("/bdpm/absents")
def get_absent_cips(db: Session = Depends(get_db)):
    """Liste les CIP marques comme absents de la BDPM."""
    return bdpm_downloader.get_absent_cips(db)


@router.delete("/bdpm/absents")
def delete_absent_cips(cip13_list: List[str], db: Session = Depends(get_db)):
    """Supprime definitivement les CIP specifies."""
    deleted = bdpm_downloader.delete_absent_cips(db, cip13_list)
    return {"deleted": deleted}


@router.post("/bdpm/upload")
async def upload_bdpm_files(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload manuel des fichiers BDPM.

    Accepte les fichiers: CIS_bdpm.txt, CIS_CIP_bdpm.txt, CIS_GENER_bdpm.txt
    Les fichiers sont sauvegardes puis integres en base.
    """
    ALLOWED_FILES = {"CIS_bdpm.txt", "CIS_CIP_bdpm.txt", "CIS_GENER_bdpm.txt"}

    results = []
    saved_files = []

    for file in files:
        if file.filename not in ALLOWED_FILES:
            results.append({
                "filename": file.filename,
                "status": "error",
                "message": f"Fichier non autorise. Fichiers acceptes: {', '.join(ALLOWED_FILES)}"
            })
            continue

        try:
            # Sauvegarder le fichier
            filepath = bdpm_downloader.BDPM_DATA_PATH / file.filename
            bdpm_downloader.ensure_data_dir()

            with open(filepath, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            saved_files.append(file.filename)
            results.append({
                "filename": file.filename,
                "status": "ok",
                "message": f"Fichier sauvegarde ({len(content)} octets)"
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "message": str(e)
            })

    # Si des fichiers ont ete sauvegardes, lancer l'integration
    integration_result = None
    if saved_files:
        try:
            integration_result = bdpm_downloader.integrate_bdpm_to_database(db)
            db.commit()
        except Exception as e:
            integration_result = {"error": str(e)}

    return {
        "files_uploaded": results,
        "integration": integration_result
    }


# =============================================================================
# ENDPOINTS RAPPROCHEMENT VENTES
# =============================================================================

@router.post("/rapprochement", response_model=RapprochementResult)
def rapprocher_ventes(
    request: RapprochementRequest,
    db: Session = Depends(get_db)
):
    """
    Rapproche les ventes avec le repertoire des generiques.

    Logique:
    - CIP trouve + Generique avec prix -> valide
    - CIP trouve + Princeps -> a_supprimer (raison: princeps)
    - CIP non trouve -> a_supprimer (raison: cip_non_trouve)
    - Sans prix -> a_supprimer (raison: sans_prix)
    """
    # Charger les ventes
    query = db.query(MesVentes)
    if request.import_id:
        query = query.filter(MesVentes.import_id == request.import_id)

    ventes = query.all()

    # Index BDPM par CIP13 pour lookup rapide (inclut tous les CIP)
    bdpm_by_cip = {}
    bdpm_all = db.query(BdpmEquivalence).all()
    for r in bdpm_all:
        bdpm_by_cip[r.cip13] = r

    # Index par libelle_groupe normalise pour fuzzy matching (seulement ceux avec groupe)
    bdpm_by_libelle = {}
    for r in bdpm_all:
        if r.libelle_groupe and r.groupe_generique_id:
            key = normalize_libelle(r.libelle_groupe)
            if key not in bdpm_by_libelle:
                bdpm_by_libelle[key] = r

    # Index par groupe_generique_id pour recuperer tous les membres
    bdpm_by_groupe = {}
    for r in bdpm_all:
        if r.groupe_generique_id:
            if r.groupe_generique_id not in bdpm_by_groupe:
                bdpm_by_groupe[r.groupe_generique_id] = []
            bdpm_by_groupe[r.groupe_generique_id].append(r)

    valides = []
    a_supprimer = []
    propositions_rattachement = []

    def creer_proposition(vente, cip13, fuzzy_bdpm, score):
        """Cree une proposition de rattachement avec tous les membres du groupe."""
        groupe_id = fuzzy_bdpm.groupe_generique_id
        membres = bdpm_by_groupe.get(groupe_id, [])

        # Trouver le prix du groupe (premier generique avec prix)
        pfht_groupe = None
        for m in membres:
            if m.pfht and m.type_generique == 1:
                pfht_groupe = float(m.pfht)
                break
        if not pfht_groupe:
            pfht_groupe = float(fuzzy_bdpm.pfht) if fuzzy_bdpm.pfht else None

        return PropositionRattachement(
            vente_id=vente.id,
            cip13=cip13,
            designation=vente.designation or "",
            quantite=vente.quantite_annuelle or 0,
            montant_ht=float(vente.montant_annuel or 0),
            groupe_generique_id=groupe_id,
            libelle_groupe=fuzzy_bdpm.libelle_groupe or "",
            fuzzy_score=score,
            membres_groupe=[
                GroupeMembre(
                    cip13=m.cip13,
                    denomination=m.denomination,
                    type_generique=m.type_generique,
                    pfht=float(m.pfht) if m.pfht else None
                )
                for m in membres
            ],
            pfht_propose=pfht_groupe
        )

    for vente in ventes:
        cip13 = vente.code_cip_achete.zfill(13) if vente.code_cip_achete else None

        # Pas de CIP -> essayer fuzzy matching
        if not cip13:
            fuzzy_result = find_fuzzy_match(vente.designation, bdpm_by_libelle, threshold=70)
            if fuzzy_result:
                fuzzy_bdpm, score = fuzzy_result
                propositions_rattachement.append(creer_proposition(vente, cip13, fuzzy_bdpm, score))
            else:
                a_supprimer.append(RapprochementResultItem(
                    vente_id=vente.id,
                    cip13=cip13,
                    designation=vente.designation or "",
                    quantite=vente.quantite_annuelle or 0,
                    montant_ht=float(vente.montant_annuel or 0),
                    status="a_supprimer",
                    raison_suppression="cip_non_trouve"
                ))
            continue

        # Chercher dans BDPM par CIP exact
        bdpm = bdpm_by_cip.get(cip13)

        if not bdpm:
            # CIP non trouve -> essayer fuzzy matching
            fuzzy_result = find_fuzzy_match(vente.designation, bdpm_by_libelle, threshold=70)
            if fuzzy_result:
                fuzzy_bdpm, score = fuzzy_result
                propositions_rattachement.append(creer_proposition(vente, cip13, fuzzy_bdpm, score))
            else:
                a_supprimer.append(RapprochementResultItem(
                    vente_id=vente.id,
                    cip13=cip13,
                    designation=vente.designation or "",
                    quantite=vente.quantite_annuelle or 0,
                    montant_ht=float(vente.montant_annuel or 0),
                    status="a_supprimer",
                    raison_suppression="cip_non_trouve"
                ))
            continue

        # CIP trouve mais sans groupe -> essayer fuzzy pour proposer rattachement
        if not bdpm.groupe_generique_id:
            fuzzy_result = find_fuzzy_match(vente.designation, bdpm_by_libelle, threshold=70)
            if fuzzy_result:
                fuzzy_bdpm, score = fuzzy_result
                propositions_rattachement.append(creer_proposition(vente, cip13, fuzzy_bdpm, score))
            else:
                # Pas de groupe et pas de fuzzy match -> a supprimer
                a_supprimer.append(RapprochementResultItem(
                    vente_id=vente.id,
                    cip13=cip13,
                    designation=vente.designation or "",
                    quantite=vente.quantite_annuelle or 0,
                    montant_ht=float(vente.montant_annuel or 0),
                    status="a_supprimer",
                    raison_suppression="cip_non_trouve",
                    pfht=float(bdpm.pfht) if bdpm.pfht else None
                ))
            continue

        # Princeps (type_generique == 0) -> a supprimer
        if bdpm.type_generique == 0:
            a_supprimer.append(RapprochementResultItem(
                vente_id=vente.id,
                cip13=cip13,
                designation=vente.designation or "",
                quantite=vente.quantite_annuelle or 0,
                montant_ht=float(vente.montant_annuel or 0),
                status="a_supprimer",
                raison_suppression="princeps",
                groupe_generique_id=bdpm.groupe_generique_id,
                type_generique=bdpm.type_generique
            ))
            continue

        # Sans prix -> a supprimer
        if not bdpm.pfht:
            a_supprimer.append(RapprochementResultItem(
                vente_id=vente.id,
                cip13=cip13,
                designation=vente.designation or "",
                quantite=vente.quantite_annuelle or 0,
                montant_ht=float(vente.montant_annuel or 0),
                status="a_supprimer",
                raison_suppression="sans_prix",
                groupe_generique_id=bdpm.groupe_generique_id,
                type_generique=bdpm.type_generique
            ))
            continue

        # CIP avec groupe + prix -> valide!
        valides.append(RapprochementResultItem(
            vente_id=vente.id,
            cip13=cip13,
            designation=vente.designation or "",
            quantite=vente.quantite_annuelle or 0,
            montant_ht=float(vente.montant_annuel or 0),
            status="valide",
            pfht=float(bdpm.pfht),
            groupe_generique_id=bdpm.groupe_generique_id,
            type_generique=bdpm.type_generique,
            match_origin="exact"
        ))

    return RapprochementResult(
        valides=valides,
        a_supprimer=a_supprimer,
        propositions_rattachement=propositions_rattachement,
        stats={
            "total_ventes": len(ventes),
            "valides": len(valides),
            "a_supprimer": len(a_supprimer),
            "propositions": len(propositions_rattachement),
            "princeps": sum(1 for i in a_supprimer if i.raison_suppression == "princeps"),
            "cip_non_trouve": sum(1 for i in a_supprimer if i.raison_suppression == "cip_non_trouve"),
            "sans_prix": sum(1 for i in a_supprimer if i.raison_suppression == "sans_prix"),
        }
    )


@router.post("/rapprochement/valider")
def valider_rapprochement(
    request: ValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Valide les resultats de rapprochement.

    Actions:
    - validate_match: Enregistre le match dans la memoire
    - delete: Supprime les ventes
    """
    if request.action == "validate_match":
        # Enregistrer les matches dans la memoire
        validated = 0
        for vente_id in request.vente_ids:
            vente = db.query(MesVentes).filter(MesVentes.id == vente_id).first()
            if vente and vente.code_cip_achete:
                # Le match a deja ete fait, on valide juste
                matching_memory.validate_cip(db, vente.code_cip_achete.zfill(13))
                validated += 1

        return {"action": "validate_match", "validated": validated}

    elif request.action == "delete":
        # Supprimer les ventes
        deleted = db.query(MesVentes).filter(
            MesVentes.id.in_(request.vente_ids)
        ).delete(synchronize_session=False)
        db.commit()
        return {"action": "delete", "deleted": deleted}

    else:
        raise HTTPException(status_code=400, detail=f"Action inconnue: {request.action}")


@router.post("/rapprochement/rattacher")
def rattacher_fuzzy(
    request: RattachementRequest,
    db: Session = Depends(get_db)
):
    """
    Valide des rattachements fuzzy proposes par le systeme.

    Pour chaque rattachement:
    - Met a jour le groupe_generique_id du CIP dans bdpm_equivalences
    - Met a jour le libelle_groupe
    - Set type_generique = 1 (generique)
    - Set match_origin = 'fuzzy' pour tracer l'origine du match

    Le badge 'Fuzzy' sera affiche partout ou ce CIP apparait.
    """
    rattaches = 0
    erreurs = []

    for item in request.rattachements:
        cip13 = item.cip13.zfill(13) if item.cip13 else None
        if not cip13:
            erreurs.append({"vente_id": item.vente_id, "erreur": "CIP manquant"})
            continue

        # Recuperer les infos du groupe propose
        groupe_ref = db.query(BdpmEquivalence).filter(
            BdpmEquivalence.groupe_generique_id == item.groupe_generique_id
        ).first()

        if not groupe_ref:
            erreurs.append({"vente_id": item.vente_id, "erreur": f"Groupe {item.groupe_generique_id} non trouve"})
            continue

        # Chercher le CIP dans bdpm_equivalences
        bdpm = db.query(BdpmEquivalence).filter(BdpmEquivalence.cip13 == cip13).first()

        if bdpm:
            # Mettre a jour le CIP existant
            bdpm.groupe_generique_id = item.groupe_generique_id
            bdpm.libelle_groupe = groupe_ref.libelle_groupe
            bdpm.type_generique = 1  # Generique
            bdpm.match_origin = 'fuzzy'
            # Copier le pfht du groupe si le CIP n'en a pas
            if not bdpm.pfht and groupe_ref.pfht:
                bdpm.pfht = groupe_ref.pfht
        else:
            # Le CIP n'existe pas dans bdpm_equivalences, on doit le creer
            # Recuperer la designation depuis la vente
            vente = db.query(MesVentes).filter(MesVentes.id == item.vente_id).first()
            denomination = vente.designation if vente else None

            new_bdpm = BdpmEquivalence(
                cip13=cip13,
                groupe_generique_id=item.groupe_generique_id,
                libelle_groupe=groupe_ref.libelle_groupe,
                type_generique=1,  # Generique
                pfht=groupe_ref.pfht,
                denomination=denomination,
                princeps_denomination=groupe_ref.princeps_denomination,
                absent_bdpm=False,
                match_origin='fuzzy'
            )
            db.add(new_bdpm)

        rattaches += 1

    db.commit()

    return {
        "rattaches": rattaches,
        "erreurs": erreurs,
        "message": f"{rattaches} CIP(s) rattache(s) avec succes"
    }


# =============================================================================
# ENDPOINTS MEMOIRE MATCHING
# =============================================================================

@router.get("/memory/stats", response_model=MemoryStats)
def get_memory_stats(db: Session = Depends(get_db)):
    """Statistiques de la memoire de matching."""
    stats = matching_memory.get_memory_stats(db)
    return MemoryStats(**stats)


@router.get("/memory/equivalents/{cip13}")
def get_equivalents(cip13: str, db: Session = Depends(get_db)):
    """Retourne tous les CIP equivalents a un CIP13."""
    return matching_memory.get_equivalents_for_cip(db, cip13)


@router.post("/memory/populate-from-bdpm")
def populate_memory_from_bdpm(db: Session = Depends(get_db)):
    """Peuple la memoire de matching depuis les groupes generiques BDPM."""
    stats = matching_memory.populate_from_bdpm(db)
    return stats
