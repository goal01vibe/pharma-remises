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
from rapidfuzz import fuzz

router = APIRouter(prefix="/repertoire", tags=["repertoire"])


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
    status: str  # 'valide', 'a_supprimer'
    pfht: Optional[float] = None  # Prix fabricant HT
    raison_suppression: Optional[str] = None  # 'princeps', 'cip_non_trouve', 'sans_prix'
    groupe_generique_id: Optional[int] = None
    type_generique: Optional[int] = None  # 0=princeps, 1=generique


class RapprochementResult(BaseModel):
    valides: List[RapprochementResultItem]  # Generiques avec prix
    a_supprimer: List[RapprochementResultItem]  # Princeps, non trouves, sans prix
    stats: dict


class ValidationRequest(BaseModel):
    vente_ids: List[int]
    action: str  # 'validate_match', 'delete'


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

    # Index BDPM par CIP13 pour lookup rapide
    bdpm_by_cip = {}
    for r in db.query(BdpmEquivalence).filter(
        BdpmEquivalence.absent_bdpm == False
    ).all():
        bdpm_by_cip[r.cip13] = r

    valides = []
    a_supprimer = []

    for vente in ventes:
        cip13 = vente.code_cip_achete.zfill(13) if vente.code_cip_achete else None

        item = RapprochementResultItem(
            vente_id=vente.id,
            cip13=cip13,
            designation=vente.designation or "",
            quantite=vente.quantite_annuelle or 0,
            montant_ht=float(vente.montant_annuel or 0),
            status="a_supprimer",
        )

        # Pas de CIP -> a supprimer
        if not cip13:
            item.raison_suppression = "cip_non_trouve"
            a_supprimer.append(item)
            continue

        # Chercher dans BDPM
        bdpm = bdpm_by_cip.get(cip13)

        if not bdpm:
            # CIP non trouve dans BDPM
            item.raison_suppression = "cip_non_trouve"
            a_supprimer.append(item)
            continue

        item.groupe_generique_id = bdpm.groupe_generique_id
        item.type_generique = bdpm.type_generique

        # Princeps -> a supprimer
        if bdpm.type_generique == 0:
            item.raison_suppression = "princeps"
            a_supprimer.append(item)
            continue

        # Sans prix -> a supprimer
        if not bdpm.pfht:
            item.raison_suppression = "sans_prix"
            a_supprimer.append(item)
            continue

        # Generique avec prix -> valide!
        item.status = "valide"
        item.pfht = float(bdpm.pfht)
        valides.append(item)

    return RapprochementResult(
        valides=valides,
        a_supprimer=a_supprimer,
        stats={
            "total_ventes": len(ventes),
            "valides": len(valides),
            "a_supprimer": len(a_supprimer),
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
