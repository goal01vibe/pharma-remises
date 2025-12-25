import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.db import get_db
from app.models import CatalogueProduit
from app.schemas import (
    CatalogueProduitCreate,
    CatalogueProduitUpdate,
    CatalogueProduitResponse,
)

router = APIRouter(prefix="/api/catalogue", tags=["Catalogue"])


def extract_molecule_name(libelle_groupe: str) -> str:
    """
    Extrait le nom de la molécule du libelle_groupe BDPM.
    Format BDPM: "MOLECULE DOSAGE - PRINCEPS DOSAGE, forme"
    Exemple: "RAMIPRIL 10 mg - TRIATEC 10 mg, comprimé" → "RAMIPRIL"
    """
    # Prendre la partie avant le tiret
    part = libelle_groupe.split(' - ')[0].strip()

    # Supprimer les dosages: X mg, X,X mg, X %, X microgrammes, etc.
    part = re.sub(r'\s+\d+[\d,\.]*\s*(mg|g|ml|%|microgrammes?|ui|mmol)\b', '', part, flags=re.IGNORECASE)

    # Supprimer les équivalences: "équivalant à ..."
    part = re.sub(r'\s+équivalant\s+à\s+.*', '', part, flags=re.IGNORECASE)

    # Supprimer les sels et formes chimiques entre parenthèses
    # mais garder les associations comme "PARACETAMOL + CODEINE"
    part = re.sub(r'\s*\([^)]*\)', '', part)

    # Nettoyer les espaces multiples
    part = re.sub(r'\s+', ' ', part).strip()

    return part.upper()


@router.get("", response_model=List[CatalogueProduitResponse])
def list_catalogue(
    laboratoire_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Liste les produits du catalogue, optionnellement filtre par labo."""
    query = db.query(CatalogueProduit).options(joinedload(CatalogueProduit.presentation))

    if laboratoire_id:
        query = query.filter(CatalogueProduit.laboratoire_id == laboratoire_id)

    return query.order_by(CatalogueProduit.nom_commercial).limit(1000).all()


@router.get("/compare/{labo1_id}/{labo2_id}")
def compare_catalogues(labo1_id: int, labo2_id: int, db: Session = Depends(get_db)):
    """
    Compare les catalogues de deux laboratoires par groupe générique BDPM.
    Retourne les groupes communs, exclusifs à chaque labo.
    """
    from app.models import Laboratoire

    # Vérifier que les labos existent
    labo1 = db.query(Laboratoire).filter(Laboratoire.id == labo1_id).first()
    labo2 = db.query(Laboratoire).filter(Laboratoire.id == labo2_id).first()

    if not labo1 or not labo2:
        raise HTTPException(status_code=404, detail="Laboratoire non trouvé")

    # Récupérer les produits de chaque labo (seulement ceux avec groupe générique)
    produits1 = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == labo1_id,
        CatalogueProduit.groupe_generique_id.isnot(None)
    ).all()
    produits2 = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == labo2_id,
        CatalogueProduit.groupe_generique_id.isnot(None)
    ).all()

    # Construire les dicts groupe_id -> libellé (prend le premier libellé trouvé)
    groupes1 = {}
    for p in produits1:
        if p.groupe_generique_id not in groupes1:
            # Extraire un libellé court: "MOLECULE DOSAGE" (avant le tiret)
            libelle = p.libelle_groupe.split(' - ')[0].strip() if p.libelle_groupe else f"Groupe {p.groupe_generique_id}"
            groupes1[p.groupe_generique_id] = libelle

    groupes2 = {}
    for p in produits2:
        if p.groupe_generique_id not in groupes2:
            libelle = p.libelle_groupe.split(' - ')[0].strip() if p.libelle_groupe else f"Groupe {p.groupe_generique_id}"
            groupes2[p.groupe_generique_id] = libelle

    set1 = set(groupes1.keys())
    set2 = set(groupes2.keys())

    # Calculer les différences
    communs_ids = set1 & set2
    only1_ids = set1 - set2
    only2_ids = set2 - set1

    # Convertir en libellés triés
    def ids_to_libelles(ids, groupes_dict):
        return sorted([groupes_dict[gid] for gid in ids])

    return {
        'labo1': {'id': labo1_id, 'nom': labo1.nom, 'total_groupes': len(set1), 'total_produits': len(produits1)},
        'labo2': {'id': labo2_id, 'nom': labo2.nom, 'total_groupes': len(set2), 'total_produits': len(produits2)},
        'communes': {
            'count': len(communs_ids),
            'molecules': ids_to_libelles(communs_ids, {**groupes1, **groupes2})
        },
        'only_labo1': {
            'count': len(only1_ids),
            'molecules': ids_to_libelles(only1_ids, groupes1)
        },
        'only_labo2': {
            'count': len(only2_ids),
            'molecules': ids_to_libelles(only2_ids, groupes2)
        }
    }


@router.get("/compare-detail/{labo1_id}/{labo2_id}")
def compare_catalogues_detail(labo1_id: int, labo2_id: int, db: Session = Depends(get_db)):
    """
    Compare les catalogues de deux laboratoires avec le détail des produits.
    Retourne les produits communs (par groupe générique) et exclusifs avec:
    - nom_commercial, code_cip, prix BDPM, prix catalogue, remise
    """
    from app.models import Laboratoire, BdpmEquivalence

    # Vérifier que les labos existent
    labo1 = db.query(Laboratoire).filter(Laboratoire.id == labo1_id).first()
    labo2 = db.query(Laboratoire).filter(Laboratoire.id == labo2_id).first()

    if not labo1 or not labo2:
        raise HTTPException(status_code=404, detail="Laboratoire non trouvé")

    # Récupérer les produits de chaque labo (seulement ceux avec groupe générique)
    produits1 = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == labo1_id,
        CatalogueProduit.groupe_generique_id.isnot(None)
    ).all()
    produits2 = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == labo2_id,
        CatalogueProduit.groupe_generique_id.isnot(None)
    ).all()

    # Récupérer les prix BDPM pour tous les CIP concernés
    all_cips = [p.code_cip for p in produits1 + produits2 if p.code_cip]
    bdpm_prices = {}
    if all_cips:
        bdpm_results = db.query(BdpmEquivalence.cip13, BdpmEquivalence.pfht).filter(
            BdpmEquivalence.cip13.in_(all_cips)
        ).all()
        bdpm_prices = {r.cip13: float(r.pfht) if r.pfht else None for r in bdpm_results}

    def product_to_dict(p):
        return {
            'id': p.id,
            'nom_commercial': p.nom_commercial,
            'code_cip': p.code_cip,
            'prix_bdpm': bdpm_prices.get(p.code_cip) if p.code_cip else (float(p.prix_fabricant) if p.prix_fabricant else None),
            'prix_catalogue': float(p.prix_ht) if p.prix_ht else None,
            'remise_pct': float(p.remise_pct) if p.remise_pct else None,
            'groupe_generique_id': p.groupe_generique_id,
            'libelle_groupe': p.libelle_groupe,
        }

    # Index par groupe générique
    groupes1 = {}
    for p in produits1:
        gid = p.groupe_generique_id
        if gid not in groupes1:
            groupes1[gid] = []
        groupes1[gid].append(product_to_dict(p))

    groupes2 = {}
    for p in produits2:
        gid = p.groupe_generique_id
        if gid not in groupes2:
            groupes2[gid] = []
        groupes2[gid].append(product_to_dict(p))

    set1 = set(groupes1.keys())
    set2 = set(groupes2.keys())

    # Calculer les différences
    communs_ids = set1 & set2
    only1_ids = set1 - set2
    only2_ids = set2 - set1

    # Construire les listes de produits
    def flatten_products(gids, groupes_dict):
        """Aplati les produits de plusieurs groupes en une seule liste triée."""
        products = []
        for gid in gids:
            products.extend(groupes_dict[gid])
        return sorted(products, key=lambda x: x['nom_commercial'] or '')

    # Pour les communs, on retourne les produits des deux labos
    communs_produits = {
        'labo1': flatten_products(communs_ids, groupes1),
        'labo2': flatten_products(communs_ids, groupes2),
    }

    return {
        'labo1': {'id': labo1_id, 'nom': labo1.nom, 'total_groupes': len(set1), 'total_produits': len(produits1)},
        'labo2': {'id': labo2_id, 'nom': labo2.nom, 'total_groupes': len(set2), 'total_produits': len(produits2)},
        'communes': {
            'count': len(communs_ids),
            'produits_labo1': communs_produits['labo1'],
            'produits_labo2': communs_produits['labo2'],
        },
        'only_labo1': {
            'count': len(only1_ids),
            'produits': flatten_products(only1_ids, groupes1),
        },
        'only_labo2': {
            'count': len(only2_ids),
            'produits': flatten_products(only2_ids, groupes2),
        }
    }


@router.get("/{produit_id}", response_model=CatalogueProduitResponse)
def get_produit(produit_id: int, db: Session = Depends(get_db)):
    """Recupere un produit par ID."""
    produit = (
        db.query(CatalogueProduit)
        .options(joinedload(CatalogueProduit.presentation))
        .filter(CatalogueProduit.id == produit_id)
        .first()
    )
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouve")
    return produit


@router.post("", response_model=CatalogueProduitResponse)
def create_produit(produit: CatalogueProduitCreate, db: Session = Depends(get_db)):
    """Cree un nouveau produit dans le catalogue."""
    db_produit = CatalogueProduit(**produit.model_dump())
    db.add(db_produit)
    db.commit()
    db.refresh(db_produit)
    return db_produit


@router.put("/{produit_id}", response_model=CatalogueProduitResponse)
def update_produit(
    produit_id: int,
    produit: CatalogueProduitUpdate,
    db: Session = Depends(get_db)
):
    """Met a jour un produit."""
    db_produit = db.query(CatalogueProduit).filter(CatalogueProduit.id == produit_id).first()
    if not db_produit:
        raise HTTPException(status_code=404, detail="Produit non trouve")

    update_data = produit.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_produit, field, value)

    db.commit()
    db.refresh(db_produit)
    return db_produit


@router.patch("/{produit_id}/remontee", response_model=CatalogueProduitResponse)
def update_remontee(
    produit_id: int,
    remontee_pct: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Met a jour le pourcentage de remontee d'un produit."""
    db_produit = db.query(CatalogueProduit).filter(CatalogueProduit.id == produit_id).first()
    if not db_produit:
        raise HTTPException(status_code=404, detail="Produit non trouve")

    db_produit.remontee_pct = remontee_pct
    db.commit()
    db.refresh(db_produit)
    return db_produit


@router.patch("/bulk/remontee")
def bulk_update_remontee(
    ids: List[int],
    remontee_pct: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Met a jour le pourcentage de remontee de plusieurs produits."""
    db.query(CatalogueProduit).filter(CatalogueProduit.id.in_(ids)).update(
        {"remontee_pct": remontee_pct},
        synchronize_session=False
    )
    db.commit()
    return {"message": f"{len(ids)} produits mis a jour"}


@router.delete("/laboratoire/{laboratoire_id}/clear")
def clear_catalogue(laboratoire_id: int, db: Session = Depends(get_db)):
    """Vide tout le catalogue d'un laboratoire."""
    count = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == laboratoire_id
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": f"{count} produits supprimes", "count": count}


@router.delete("/{produit_id}")
def delete_produit(produit_id: int, db: Session = Depends(get_db)):
    """Supprime un produit du catalogue."""
    db_produit = db.query(CatalogueProduit).filter(CatalogueProduit.id == produit_id).first()
    if not db_produit:
        raise HTTPException(status_code=404, detail="Produit non trouve")

    db.delete(db_produit)
    db.commit()
    return {"message": "Produit supprime"}


# =====================
# ENRICHISSEMENT BDPM
# =====================

@router.post("/enrich-bdpm/{laboratoire_id}")
def enrich_catalogue_bdpm(laboratoire_id: int, db: Session = Depends(get_db)):
    """
    Enrichit le catalogue d'un labo avec les prix BDPM.
    Met a jour prix_fabricant depuis BdpmEquivalence via CIP13.
    """
    from app.models import Laboratoire
    from app.services.bdpm_lookup import enrich_catalogue_with_bdpm

    labo = db.query(Laboratoire).filter(Laboratoire.id == laboratoire_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    stats = enrich_catalogue_with_bdpm(db, laboratoire_id)

    return {
        "success": True,
        "labo_id": laboratoire_id,
        "labo_nom": labo.nom,
        **stats
    }


@router.post("/enrich-bdpm-all")
def enrich_all_catalogues_bdpm(
    exclude_labo_names: List[str] = Query(default=[]),
    db: Session = Depends(get_db)
):
    """
    Enrichit les catalogues de TOUS les labos avec les prix BDPM.

    Args:
        exclude_labo_names: Liste des noms de labos a exclure (ex: "Zentiva 2026")
    """
    from app.models import Laboratoire
    from app.services.bdpm_lookup import enrich_all_catalogues_with_bdpm

    # Trouver les IDs des labos a exclure par nom
    exclude_ids = []
    if exclude_labo_names:
        for name in exclude_labo_names:
            labo = db.query(Laboratoire).filter(
                Laboratoire.nom.ilike(f"%{name}%")
            ).first()
            if labo:
                exclude_ids.append(labo.id)

    results = enrich_all_catalogues_with_bdpm(db, exclude_labo_ids=exclude_ids)

    return {
        "success": True,
        "excluded_labo_ids": exclude_ids,
        **results
    }
