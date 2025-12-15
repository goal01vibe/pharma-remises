"""
Service de lookup et enrichissement BDPM pour les ventes.

Permet de:
- Trouver le prix BDPM (PFHT) et groupe generique d'un CIP13
- Enrichir toutes les ventes d'un import avec les donnees BDPM
"""
from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models import MesVentes, BdpmEquivalence
from app.utils.logger import import_ventes_logger, OperationMetrics


def normalize_cip(cip: Optional[str]) -> Optional[str]:
    """
    Normalise un code CIP en CIP13.

    Extrait uniquement les chiffres et prend les 13 derniers caracteres.
    Gere les formats: CIP13, CIP7, ACL, EAN13, etc.
    """
    if not cip:
        return None

    # Extraire uniquement les chiffres
    digits = ''.join(c for c in str(cip) if c.isdigit())

    if not digits:
        return None

    # Si moins de 13 chiffres, padder a gauche avec des zeros
    if len(digits) < 13:
        digits = digits.zfill(13)

    # Prendre les 13 derniers chiffres (cas EAN14, etc.)
    return digits[-13:]


def lookup_bdpm_by_cip(db: Session, cip: str) -> Tuple[Optional[Decimal], Optional[int], Optional[str]]:
    """
    Recherche les informations BDPM pour un code CIP.

    Args:
        db: Session SQLAlchemy
        cip: Code CIP (sera normalise en CIP13)

    Returns:
        Tuple (prix_bdpm, groupe_generique_id, libelle_groupe)
        Retourne (None, None, None) si non trouve
    """
    cip13 = normalize_cip(cip)

    if not cip13:
        return None, None, None

    bdpm = db.query(BdpmEquivalence).filter(
        BdpmEquivalence.cip13 == cip13
    ).first()

    if bdpm:
        return bdpm.pfht, bdpm.groupe_generique_id, bdpm.libelle_groupe

    return None, None, None


def enrich_ventes_with_bdpm(db: Session, import_id: int) -> dict:
    """
    Enrichit toutes les ventes d'un import avec les donnees BDPM.

    Pour chaque vente, recherche dans BdpmEquivalence via CIP13:
    - prix_bdpm: Prix Fabricant HT de reference
    - groupe_generique_id: Pour matching instantane
    - has_bdpm_price: Flag pour identifier les ventes incompletes

    Args:
        db: Session SQLAlchemy
        import_id: ID de l'import a enrichir

    Returns:
        dict avec stats: {total, enriched, missing, errors}
    """
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()

    stats = {
        "total": len(ventes),
        "enriched": 0,
        "missing": 0,
        "errors": 0
    }

    if not ventes:
        return stats

    # Metrics pour logging
    metrics = OperationMetrics(
        import_ventes_logger,
        "bdpm_enrichment",
        total_items=len(ventes),
        batch_size=500
    )
    metrics.start(import_id=import_id)

    for vente in ventes:
        try:
            if vente.code_cip_achete:
                prix_bdpm, groupe_id, _ = lookup_bdpm_by_cip(db, vente.code_cip_achete)

                if prix_bdpm is not None:
                    vente.prix_bdpm = prix_bdpm
                    vente.has_bdpm_price = True
                    vente.groupe_generique_id = groupe_id
                    stats["enriched"] += 1
                    metrics.increment(success=True)
                else:
                    vente.has_bdpm_price = False
                    vente.groupe_generique_id = groupe_id  # Peut avoir groupe meme sans prix
                    stats["missing"] += 1
                    metrics.increment(success=False)
            else:
                vente.has_bdpm_price = False
                stats["missing"] += 1
                metrics.increment(success=False)

        except Exception as e:
            import_ventes_logger.error(f"Erreur enrichissement vente {vente.id}: {e}")
            stats["errors"] += 1
            metrics.increment(success=False)

    db.commit()
    metrics.finish(**stats)

    return stats


def get_incomplete_ventes(db: Session, import_id: int) -> list:
    """
    Retourne les ventes sans prix BDPM pour un import.
    """
    return db.query(MesVentes).filter(
        MesVentes.import_id == import_id,
        MesVentes.has_bdpm_price == False
    ).all()


def delete_incomplete_ventes(db: Session, import_id: int) -> int:
    """
    Supprime les ventes sans prix BDPM pour un import.

    Returns:
        Nombre de ventes supprimees
    """
    deleted = db.query(MesVentes).filter(
        MesVentes.import_id == import_id,
        MesVentes.has_bdpm_price == False
    ).delete()

    db.commit()
    import_ventes_logger.info(f"Supprime {deleted} ventes incompletes pour import {import_id}")

    return deleted


# =====================
# ENRICHISSEMENT CATALOGUES
# =====================

def enrich_catalogue_with_bdpm(db: Session, laboratoire_id: int) -> dict:
    """
    Enrichit tous les produits d'un catalogue avec les prix BDPM.

    Pour chaque produit du catalogue:
    - Lookup prix BDPM via CIP13 dans BdpmEquivalence
    - Met a jour prix_fabricant avec le pfht BDPM
    - Met a jour groupe_generique_id et libelle_groupe si non definis

    Args:
        db: Session SQLAlchemy
        laboratoire_id: ID du laboratoire dont enrichir le catalogue

    Returns:
        dict avec stats: {total, enriched, already_has_price, missing, errors}
    """
    from app.models import CatalogueProduit

    produits = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == laboratoire_id
    ).all()

    stats = {
        "total": len(produits),
        "enriched": 0,
        "already_has_price": 0,
        "missing": 0,
        "errors": 0
    }

    if not produits:
        return stats

    for produit in produits:
        try:
            # Skip si deja un prix_fabricant
            if produit.prix_fabricant is not None:
                stats["already_has_price"] += 1
                continue

            if produit.code_cip:
                prix_bdpm, groupe_id, libelle = lookup_bdpm_by_cip(db, produit.code_cip)

                if prix_bdpm is not None:
                    produit.prix_fabricant = prix_bdpm
                    stats["enriched"] += 1

                    # Mettre a jour groupe si non defini
                    if produit.groupe_generique_id is None and groupe_id:
                        produit.groupe_generique_id = groupe_id
                    if produit.libelle_groupe is None and libelle:
                        produit.libelle_groupe = libelle
                else:
                    stats["missing"] += 1
            else:
                stats["missing"] += 1

        except Exception as e:
            import_ventes_logger.error(f"Erreur enrichissement produit {produit.id}: {e}")
            stats["errors"] += 1

    db.commit()
    import_ventes_logger.info(
        f"Enrichissement catalogue labo {laboratoire_id}: "
        f"{stats['enriched']} enrichis, {stats['already_has_price']} deja avec prix, "
        f"{stats['missing']} non trouves"
    )

    return stats


def enrich_all_catalogues_with_bdpm(db: Session, exclude_labo_ids: list = None) -> dict:
    """
    Enrichit les catalogues de TOUS les labos avec les prix BDPM.

    Args:
        db: Session SQLAlchemy
        exclude_labo_ids: Liste des IDs de labos a exclure

    Returns:
        dict avec stats par labo et totaux
    """
    from app.models import Laboratoire

    exclude_labo_ids = exclude_labo_ids or []

    labos = db.query(Laboratoire).filter(
        Laboratoire.id.notin_(exclude_labo_ids) if exclude_labo_ids else True
    ).all()

    results = {
        "labos": [],
        "totaux": {
            "total": 0,
            "enriched": 0,
            "already_has_price": 0,
            "missing": 0,
            "errors": 0
        }
    }

    for labo in labos:
        stats = enrich_catalogue_with_bdpm(db, labo.id)
        results["labos"].append({
            "labo_id": labo.id,
            "labo_nom": labo.nom,
            **stats
        })

        # Aggreger les totaux
        for key in ["total", "enriched", "already_has_price", "missing", "errors"]:
            results["totaux"][key] += stats[key]

    return results
