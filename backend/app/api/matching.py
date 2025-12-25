"""API endpoints pour le matching intelligent des ventes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import time
from decimal import Decimal

from app.db import get_db
from app.utils.logger import matching_logger, OperationMetrics
from app.models import MesVentes, Import, Laboratoire, CatalogueProduit, VenteMatching
from app.schemas import (
    ProcessSalesRequest,
    ProcessSalesResponse,
    AnalyzeMatchRequest,
    AnalyzeMatchResponse,
    MatchResultItem,
    ExtractedComponents,
)
from app.services.intelligent_matching import IntelligentMatcher, MoleculeExtractor

router = APIRouter(prefix="/api/matching", tags=["Matching Intelligent"])


# Labos cibles (5 labos generiques principaux)
TARGET_LABS = ["BIOGARAN", "SANDOZ", "ARROW", "ZENTIVA", "VIATRIS"]


def get_matching_stats_internal(db: Session, import_id: int) -> dict:
    """
    Fonction interne pour recuperer les stats de matching.
    Utilisee pour le cache et l'endpoint /stats.
    """
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    vente_ids = [v.id for v in ventes]

    if not vente_ids:
        return {"matched": 0, "unmatched": 0, "by_lab": []}

    matchings = db.query(VenteMatching).filter(VenteMatching.vente_id.in_(vente_ids)).all()

    if not matchings:
        return {"matched": 0, "unmatched": len(ventes), "by_lab": []}

    # Stats par labo
    by_lab = {}
    matched_ventes = set()

    for m in matchings:
        if m.labo_id not in by_lab:
            labo = db.query(Laboratoire).filter(Laboratoire.id == m.labo_id).first()
            by_lab[m.labo_id] = {
                "lab_id": m.labo_id,
                "lab_nom": labo.nom if labo else "?",
                "matched_count": 0,
                "total_montant": Decimal("0")
            }

        vente = next((v for v in ventes if v.id == m.vente_id), None)
        if vente:
            by_lab[m.labo_id]["matched_count"] += 1
            by_lab[m.labo_id]["total_montant"] += vente.montant_annuel or Decimal("0")
            matched_ventes.add(m.vente_id)

    # Construire la liste
    total_ventes = len(ventes)
    by_lab_list = []
    for lab_id, stats in by_lab.items():
        couverture = stats["matched_count"] / total_ventes * 100 if total_ventes > 0 else 0
        by_lab_list.append({
            "lab_id": stats["lab_id"],
            "lab_nom": stats["lab_nom"],
            "matched_count": stats["matched_count"],
            "total_montant_matched": float(stats["total_montant"]),
            "couverture_pct": round(couverture, 1)
        })

    by_lab_list.sort(key=lambda x: x["matched_count"], reverse=True)

    return {
        "matched": len(matched_ventes),
        "unmatched": total_ventes - len(matched_ventes),
        "by_lab": by_lab_list
    }


@router.post("/process-sales", response_model=ProcessSalesResponse)
def process_sales_matching(
    request: ProcessSalesRequest,
    force_rematch: bool = False,
    db: Session = Depends(get_db)
):
    """
    Lance le matching intelligent des ventes importees.

    OPTIMISATION: Utilise groupe_generique_id (jointure SQL instantanee)
    avant de recourir au fuzzy matching (lent).

    Pour chaque vente de l'import, trouve l'equivalent dans les labos cibles.
    Stocke les resultats dans la table vente_matching.

    Args:
        request: import_id et min_score
        force_rematch: Si False et matching existe, retourne le cache

    Returns:
        Stats du matching: nb matches, unmatched, couverture par labo
    """
    start_time = time.time()

    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == request.import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")
    if import_obj.type_import != "ventes":
        raise HTTPException(status_code=400, detail="L'import doit etre de type 'ventes'")

    # Recuperer les ventes de cet import
    ventes = db.query(MesVentes).filter(MesVentes.import_id == request.import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente trouvee pour cet import")

    vente_ids = [v.id for v in ventes]

    # === CACHE CHECK: Si matching existe et pas force_rematch, retourner stats ===
    if not force_rematch:
        existing_matchings = db.query(VenteMatching).filter(
            VenteMatching.vente_id.in_(vente_ids)
        ).first()

        if existing_matchings:
            # Matching existe deja, retourner les stats depuis le cache
            matching_logger.info(f"Matching cache trouve pour import {request.import_id}, utilisation du cache")
            stats = get_matching_stats_internal(db, request.import_id)
            elapsed = time.time() - start_time
            return ProcessSalesResponse(
                import_id=request.import_id,
                total_ventes=len(ventes),
                matching_results=stats,
                unmatched_products=[],
                processing_time_s=round(elapsed, 2),
                cached=True
            )

    # Recuperer les labos cibles (filtrer par labo_ids si fourni)
    if request.labo_ids:
        # Utiliser les labos specifies
        labos = db.query(Laboratoire).filter(Laboratoire.id.in_(request.labo_ids)).all()
    else:
        # Tous les labos cibles par defaut
        labos = db.query(Laboratoire).filter(Laboratoire.nom.in_(TARGET_LABS)).all()

    if not labos:
        raise HTTPException(status_code=404, detail="Aucun labo cible trouve. Lancez d'abord l'import BDPM.")

    labo_ids = [l.id for l in labos]
    labo_map = {l.id: l for l in labos}

    # === LOGGING: Initialiser les métriques ===
    total_ventes = len(ventes)
    metrics = OperationMetrics(
        matching_logger,
        "process_sales_matching",
        total_items=total_ventes * len(labos),  # ventes x labos
        batch_size=500  # Log tous les 500 matchings
    )
    metrics.start(
        import_id=request.import_id,
        nb_ventes=total_ventes,
        nb_labos=len(labos),
        labos=[l.nom for l in labos],
        min_score=request.min_score,
        force_rematch=force_rematch
    )

    # Initialiser le matcher
    matcher = IntelligentMatcher(db)

    # === INVALIDATION CACHE si force_rematch ===
    if force_rematch:
        matcher.clear_cache()
        matching_logger.info(f"Cache IntelligentMatcher invalide pour force_rematch")

    # Supprimer les anciens matchings pour cet import
    db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids)
    ).delete(synchronize_session=False)
    db.commit()
    matching_logger.debug(f"Anciens matchings supprimes pour import {request.import_id}")

    # === OPTIMISATION: Pre-indexer les produits ===
    # 1. Index par CIP pour matching exact (prioritaire)
    products_by_cip = {}
    # 2. Index par groupe_generique_id pour matching groupe
    products_by_groupe = {}

    for labo_id in labo_ids:
        products = db.query(CatalogueProduit).filter(
            CatalogueProduit.laboratoire_id == labo_id,
            CatalogueProduit.actif == True
        ).all()
        for p in products:
            # Index par CIP (pour matching exact)
            if p.code_cip:
                cip_key = (p.code_cip, labo_id)
                products_by_cip[cip_key] = p

            # Index par groupe_generique
            if p.groupe_generique_id:
                groupe_key = (p.groupe_generique_id, labo_id)
                if groupe_key not in products_by_groupe:
                    products_by_groupe[groupe_key] = []
                products_by_groupe[groupe_key].append(p)

    # Log index sizes
    matching_logger.debug(f"Index CIP: {len(products_by_cip)} produits, Index Groupe: {len(products_by_groupe)} groupes")

    # Stats
    matched_ventes = set()
    unmatched_products = []
    by_lab_stats = {l.id: {"lab_id": l.id, "lab_nom": l.nom, "matched_count": 0, "total_montant": Decimal("0")} for l in labos}

    # Compteurs pour stats de type de matching
    match_type_stats = {"exact_cip": 0, "groupe_generique": 0, "fuzzy": 0, "no_match": 0}

    # Matcher chaque vente
    for vente in ventes:
        designation = vente.designation or ""
        code_cip = vente.code_cip_achete
        groupe_id = vente.groupe_generique_id  # Enrichi par BDPM

        if not designation and not code_cip:
            unmatched_products.append({
                "vente_id": vente.id,
                "designation": designation,
                "montant": float(vente.montant_annuel or 0),
                "reason": "Designation et code CIP manquants"
            })
            match_type_stats["no_match"] += 1
            continue

        # Trouver les matches dans tous les labos
        has_match = False

        for labo_id in labo_ids:
            matched_product = None
            match_type = None
            match_score = 0.0

            # === PRIORITE 1: Matching CIP EXACT (le plus fiable) ===
            if code_cip:
                cip_key = (code_cip, labo_id)
                if cip_key in products_by_cip:
                    matched_product = products_by_cip[cip_key]
                    match_type = "exact_cip"
                    match_score = 100.0

            # === PRIORITE 2: Matching par groupe_generique avec verification conditionnement ===
            if not matched_product and groupe_id:
                groupe_key = (groupe_id, labo_id)
                if groupe_key in products_by_groupe:
                    candidates = products_by_groupe[groupe_key]

                    # Extraire le conditionnement de la vente si disponible
                    vente_cond = getattr(vente, 'conditionnement', None)

                    # Chercher un produit avec le meme conditionnement
                    best_match = None
                    for prod in candidates:
                        prod_cond = getattr(prod, 'conditionnement', None)
                        if vente_cond and prod_cond and vente_cond == prod_cond:
                            best_match = prod
                            break

                    # Si pas de match exact sur conditionnement, prendre le premier
                    if best_match:
                        matched_product = best_match
                        match_type = "groupe_generique"
                        match_score = 100.0
                    elif candidates:
                        # Match par groupe mais conditionnement different
                        matched_product = candidates[0]
                        match_type = "groupe_generique"
                        match_score = 95.0  # Score reduit car conditionnement non verifie

            # === PRIORITE 3: Fuzzy matching (fallback) ===
            if not matched_product:
                matches = matcher.find_matches_for_product(
                    designation=designation,
                    code_cip=code_cip,
                    target_lab_id=labo_id
                )
                if matches and matches[0].score >= request.min_score:
                    best = matches[0]
                    matched_product = db.query(CatalogueProduit).filter(
                        CatalogueProduit.id == best.produit_id
                    ).first()
                    match_type = best.match_type
                    match_score = best.score

            # === LOGGING: Incrementer compteur ===
            metrics.increment(success=bool(matched_product))

            if matched_product:
                # Stocker le matching
                vm = VenteMatching(
                    vente_id=vente.id,
                    labo_id=labo_id,
                    produit_id=matched_product.id,
                    match_score=Decimal(str(match_score)),
                    match_type=match_type,
                    matched_on=f"Groupe {groupe_id}" if match_type == "groupe_generique" else None
                )
                db.add(vm)
                has_match = True
                matched_ventes.add(vente.id)
                by_lab_stats[labo_id]["matched_count"] += 1
                by_lab_stats[labo_id]["total_montant"] += vente.montant_annuel or Decimal("0")

                # Stats par type
                if match_type == "exact_cip":
                    match_type_stats["exact_cip"] += 1
                elif match_type == "groupe_generique":
                    match_type_stats["groupe_generique"] += 1
                else:
                    match_type_stats["fuzzy"] += 1

        if not has_match:
            unmatched_products.append({
                "vente_id": vente.id,
                "designation": designation,
                "montant": float(vente.montant_annuel or 0),
                "has_groupe_id": groupe_id is not None,
                "groupe_id": groupe_id
            })
            match_type_stats["no_match"] += 1

    db.commit()

    # Calculer le montant total des ventes
    total_montant = sum(v.montant_annuel or Decimal("0") for v in ventes)

    # Construire la response
    by_lab_list = []
    for labo_id, stats in by_lab_stats.items():
        couverture = (stats["matched_count"] / total_ventes * 100) if total_ventes > 0 else 0
        by_lab_list.append({
            "lab_id": stats["lab_id"],
            "lab_nom": stats["lab_nom"],
            "matched_count": stats["matched_count"],
            "total_montant_matched": float(stats["total_montant"]),
            "couverture_pct": round(couverture, 1)
        })

    # Trier par couverture decroissante
    by_lab_list.sort(key=lambda x: x["matched_count"], reverse=True)

    elapsed = time.time() - start_time

    # === LOGGING: Finaliser les métriques ===
    metrics.finish(
        matched_ventes=len(matched_ventes),
        unmatched_ventes=total_ventes - len(matched_ventes),
        best_labo=by_lab_list[0]["lab_nom"] if by_lab_list else "N/A",
        best_couverture=by_lab_list[0]["couverture_pct"] if by_lab_list else 0,
        match_by_groupe=match_type_stats["groupe_generique"],
        match_by_fuzzy=match_type_stats["fuzzy"],
        no_match=match_type_stats["no_match"]
    )

    return ProcessSalesResponse(
        import_id=request.import_id,
        total_ventes=total_ventes,
        matching_results={
            "matched": len(matched_ventes),
            "unmatched": total_ventes - len(matched_ventes),
            "by_lab": by_lab_list,
            "match_type_stats": match_type_stats
        },
        unmatched_products=unmatched_products[:50],  # Limiter a 50 pour la response
        processing_time_s=round(elapsed, 2)
    )


@router.post("/analyze", response_model=AnalyzeMatchResponse)
def analyze_match(
    request: AnalyzeMatchRequest,
    db: Session = Depends(get_db)
):
    """
    Analyse le matching pour une designation specifique.

    Utile pour debug et comprendre pourquoi un produit matche ou non.

    Args:
        request: designation et optionnel code_cip

    Returns:
        Composants extraits et matches par labo
    """
    # Extraire les composants
    extractor = MoleculeExtractor()
    components = extractor.extract_from_commercial_name(request.designation)

    # Recuperer les labos cibles
    labos = db.query(Laboratoire).filter(Laboratoire.nom.in_(TARGET_LABS)).all()
    labo_map = {l.id: l for l in labos}

    # Initialiser le matcher
    matcher = IntelligentMatcher(db)

    # Trouver les matches dans tous les labos
    matches_by_lab = []
    for labo in labos:
        matches = matcher.find_matches_for_product(
            designation=request.designation,
            code_cip=request.code_cip,
            target_lab_id=labo.id
        )

        for m in matches[:3]:  # Top 3 par labo
            produit = db.query(CatalogueProduit).filter(CatalogueProduit.id == m.produit_id).first()
            matches_by_lab.append(MatchResultItem(
                produit_id=m.produit_id,
                labo_id=labo.id,
                labo_nom=labo.nom,
                nom_commercial=m.nom_commercial,
                code_cip=produit.code_cip if produit else None,
                score=m.score,
                match_type=m.match_type,
                matched_on=m.matched_on,
                prix_ht=produit.prix_ht if produit else None,
                remise_pct=produit.remise_pct if produit else None
            ))

    # Trier par score decroissant
    matches_by_lab.sort(key=lambda x: x.score, reverse=True)

    return AnalyzeMatchResponse(
        extracted=ExtractedComponents(
            molecule=components.molecule,
            dosage=components.dosage,
            forme=components.forme,
            conditionnement=components.conditionnement
        ),
        matches_by_lab=matches_by_lab
    )


@router.get("/stats/{import_id}")
def get_matching_stats(
    import_id: int,
    db: Session = Depends(get_db)
):
    """
    Recupere les statistiques de matching pour un import.

    Utile pour voir la couverture par labo apres le matching.
    """
    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Recuperer les ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    vente_ids = [v.id for v in ventes]

    if not vente_ids:
        return {"import_id": import_id, "total_ventes": 0, "matching_done": False}

    # Recuperer les matchings
    matchings = db.query(VenteMatching).filter(VenteMatching.vente_id.in_(vente_ids)).all()

    if not matchings:
        return {
            "import_id": import_id,
            "total_ventes": len(ventes),
            "matching_done": False,
            "message": "Matching non effectue. Lancez POST /api/matching/process-sales"
        }

    # Stats par labo
    by_lab = {}
    matched_ventes = set()

    for m in matchings:
        if m.labo_id not in by_lab:
            labo = db.query(Laboratoire).filter(Laboratoire.id == m.labo_id).first()
            by_lab[m.labo_id] = {
                "lab_id": m.labo_id,
                "lab_nom": labo.nom if labo else "?",
                "matched_count": 0,
                "total_montant": Decimal("0"),
                "avg_score": []
            }

        vente = next((v for v in ventes if v.id == m.vente_id), None)
        if vente:
            by_lab[m.labo_id]["matched_count"] += 1
            by_lab[m.labo_id]["total_montant"] += vente.montant_annuel or Decimal("0")
            by_lab[m.labo_id]["avg_score"].append(float(m.match_score or 0))
            matched_ventes.add(m.vente_id)

    # Calculer moyennes
    total_montant = sum(v.montant_annuel or Decimal("0") for v in ventes)
    by_lab_list = []
    for lab_id, stats in by_lab.items():
        avg_score = sum(stats["avg_score"]) / len(stats["avg_score"]) if stats["avg_score"] else 0
        couverture_count = stats["matched_count"] / len(ventes) * 100 if ventes else 0
        couverture_montant = float(stats["total_montant"]) / float(total_montant) * 100 if total_montant > 0 else 0

        by_lab_list.append({
            "lab_id": stats["lab_id"],
            "lab_nom": stats["lab_nom"],
            "matched_count": stats["matched_count"],
            "total_montant_matched": float(stats["total_montant"]),
            "couverture_count_pct": round(couverture_count, 1),
            "couverture_montant_pct": round(couverture_montant, 1),
            "avg_match_score": round(avg_score, 1)
        })

    by_lab_list.sort(key=lambda x: x["matched_count"], reverse=True)

    return {
        "import_id": import_id,
        "total_ventes": len(ventes),
        "total_montant_ht": float(total_montant),
        "matching_done": True,
        "matched_ventes": len(matched_ventes),
        "unmatched_ventes": len(ventes) - len(matched_ventes),
        "by_lab": by_lab_list
    }


@router.delete("/clear/{import_id}")
def clear_matching(
    import_id: int,
    db: Session = Depends(get_db)
):
    """
    Supprime les matchings pour un import.

    Utile pour relancer le matching avec de nouveaux parametres.
    """
    # Recuperer les ventes de l'import
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    vente_ids = [v.id for v in ventes]

    if not vente_ids:
        return {"deleted": 0}

    # Supprimer les matchings
    deleted = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids)
    ).delete(synchronize_session=False)
    db.commit()

    return {"deleted": deleted}


@router.get("/details/{import_id}/{labo_id}")
def get_matching_details(
    import_id: int,
    labo_id: int,
    db: Session = Depends(get_db)
):
    """
    Retourne le detail du matching pour un import et un labo specifique.

    Inclut toutes les ventes avec leur statut de matching (matche ou non).
    Mode debug: toutes les infos techniques.
    """
    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Recuperer toutes les ventes de l'import
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()

    # Recuperer les matchings pour ce labo
    vente_ids = [v.id for v in ventes]
    matchings = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids),
        VenteMatching.labo_id == labo_id
    ).all()

    # Creer un dict pour lookup rapide
    matching_by_vente = {m.vente_id: m for m in matchings}

    # OPTIMISATION: Recuperer tous les produits en UNE SEULE requete (evite N+1)
    produit_ids = [m.produit_id for m in matchings if m.produit_id]
    if produit_ids:
        produits = db.query(CatalogueProduit).filter(
            CatalogueProduit.id.in_(produit_ids)
        ).all()
        produits_by_id = {p.id: p for p in produits}
    else:
        produits_by_id = {}

    # Construire la liste de details
    details = []
    matched_count = 0
    unmatched_count = 0

    for vente in ventes:
        matching = matching_by_vente.get(vente.id)

        if matching:
            matched_count += 1
            # Lookup rapide du produit (plus de requete SQL ici)
            produit = produits_by_id.get(matching.produit_id)

            details.append({
                "vente_id": vente.id,
                "matched": True,
                # Infos vente
                "vente_designation": vente.designation,
                "vente_code_cip": vente.code_cip_achete,
                "vente_quantite": vente.quantite_annuelle,
                "vente_labo_actuel": vente.labo_actuel,
                # Infos produit matche
                "produit_id": produit.id if produit else None,
                "produit_nom": produit.nom_commercial if produit else None,
                "produit_code_cip": produit.code_cip if produit else None,
                "produit_prix_ht": float(produit.prix_ht) if produit and produit.prix_ht else None,
                "produit_remise_pct": float(produit.remise_pct) if produit and produit.remise_pct else None,
                "produit_groupe_generique_id": produit.groupe_generique_id if produit else None,
                "produit_libelle_groupe": produit.libelle_groupe if produit else None,
                # Infos matching
                "match_score": float(matching.match_score) if matching.match_score else None,
                "match_type": matching.match_type,
                "matched_on": matching.matched_on,
            })
        else:
            unmatched_count += 1
            details.append({
                "vente_id": vente.id,
                "matched": False,
                # Infos vente
                "vente_designation": vente.designation,
                "vente_code_cip": vente.code_cip_achete,
                "vente_quantite": vente.quantite_annuelle,
                "vente_labo_actuel": vente.labo_actuel,
                # Pas de produit matche
                "produit_id": None,
                "produit_nom": None,
                "produit_code_cip": None,
                "produit_prix_ht": None,
                "produit_remise_pct": None,
                "produit_groupe_generique_id": None,
                "produit_libelle_groupe": None,
                "match_score": None,
                "match_type": None,
                "matched_on": None,
            })

    # Trier: non matches en premier, puis par designation
    details.sort(key=lambda x: (x["matched"], x["vente_designation"] or ""))

    return {
        "import_id": import_id,
        "labo_id": labo_id,
        "labo_nom": labo.nom,
        "total_ventes": len(ventes),
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "couverture_pct": round(matched_count / len(ventes) * 100, 1) if ventes else 0,
        "details": details
    }


@router.get("/search-products/{labo_id}")
def search_products_in_labo(
    labo_id: int,
    q: str,
    db: Session = Depends(get_db)
):
    """
    Recherche des produits dans le catalogue d'un labo.

    Utilise pour la correction manuelle du matching.
    """
    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Recherche par nom ou code CIP
    products = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == labo_id,
        (
            CatalogueProduit.nom_commercial.ilike(f"%{q}%") |
            CatalogueProduit.code_cip.ilike(f"%{q}%") |
            CatalogueProduit.libelle_groupe.ilike(f"%{q}%")
        )
    ).limit(20).all()

    return {
        "labo_id": labo_id,
        "labo_nom": labo.nom,
        "query": q,
        "results": [
            {
                "id": p.id,
                "nom_commercial": p.nom_commercial,
                "code_cip": p.code_cip,
                "prix_ht": float(p.prix_ht) if p.prix_ht else None,
                "remise_pct": float(p.remise_pct) if p.remise_pct else None,
                "groupe_generique_id": p.groupe_generique_id,
                "libelle_groupe": p.libelle_groupe,
            }
            for p in products
        ]
    }


@router.put("/manual/{vente_id}/{labo_id}")
def set_manual_matching(
    vente_id: int,
    labo_id: int,
    produit_id: int,
    db: Session = Depends(get_db)
):
    """
    Definit ou modifie manuellement un matching.

    Permet de corriger un matching incorrect ou d'ajouter un matching manquant.
    """
    # Verifier la vente
    vente = db.query(MesVentes).filter(MesVentes.id == vente_id).first()
    if not vente:
        raise HTTPException(status_code=404, detail="Vente non trouvee")

    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Verifier le produit
    produit = db.query(CatalogueProduit).filter(
        CatalogueProduit.id == produit_id,
        CatalogueProduit.laboratoire_id == labo_id
    ).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouve dans ce laboratoire")

    # Chercher un matching existant
    existing = db.query(VenteMatching).filter(
        VenteMatching.vente_id == vente_id,
        VenteMatching.labo_id == labo_id
    ).first()

    if existing:
        # Mettre a jour
        existing.produit_id = produit_id
        existing.match_score = Decimal("100")  # Score manuel = 100%
        existing.match_type = "manual"
        existing.matched_on = f"Correction manuelle: {produit.nom_commercial}"
    else:
        # Creer nouveau
        vm = VenteMatching(
            vente_id=vente_id,
            labo_id=labo_id,
            produit_id=produit_id,
            match_score=Decimal("100"),
            match_type="manual",
            matched_on=f"Correction manuelle: {produit.nom_commercial}"
        )
        db.add(vm)

    db.commit()

    return {
        "success": True,
        "vente_id": vente_id,
        "labo_id": labo_id,
        "produit_id": produit_id,
        "produit_nom": produit.nom_commercial,
        "message": "Matching mis a jour" if existing else "Matching cree"
    }


@router.delete("/manual/{vente_id}/{labo_id}")
def delete_manual_matching(
    vente_id: int,
    labo_id: int,
    db: Session = Depends(get_db)
):
    """
    Supprime un matching specifique.
    """
    deleted = db.query(VenteMatching).filter(
        VenteMatching.vente_id == vente_id,
        VenteMatching.labo_id == labo_id
    ).delete()
    db.commit()

    return {
        "success": True,
        "deleted": deleted
    }
