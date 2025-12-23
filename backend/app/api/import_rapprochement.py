"""
Import avec rapprochement - Preview et confirmation.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import pandas as pd
import io
import time
import hashlib

from rapidfuzz import fuzz

from app.db import get_db
from app.models import CatalogueProduit, Laboratoire

router = APIRouter(prefix="/api/import", tags=["Import Rapprochement"])

# Cache temporaire pour stocker les previews (en production, utiliser Redis)
_import_preview_cache: Dict[str, Dict] = {}


def _clean_cip(cip: str) -> str:
    """Nettoie un code CIP (garde uniquement les chiffres)."""
    if not cip:
        return ""
    return "".join(c for c in str(cip) if c.isdigit())


def _normalize_name(name: str) -> str:
    """Normalise un nom de produit pour comparaison."""
    if not name:
        return ""
    return name.upper().strip()


def _match_product(
    code_cip: str,
    designation: str,
    existing_products: List[CatalogueProduit],
    cip_index: Dict[str, CatalogueProduit],
) -> tuple:
    """
    Trouve un produit existant qui correspond.
    Retourne (produit, match_type, score).
    """
    clean_cip = _clean_cip(code_cip)

    # 1. Match exact par CIP
    if clean_cip and clean_cip in cip_index:
        return cip_index[clean_cip], "cip_exact", 100.0

    # 2. Match fuzzy par nom
    if designation:
        norm_name = _normalize_name(designation)
        best_match = None
        best_score = 0.0

        for prod in existing_products:
            if prod.nom_commercial:
                prod_norm = _normalize_name(prod.nom_commercial)
                # Utilise WRatio pour gerer les mots dans le desordre
                score = fuzz.WRatio(norm_name, prod_norm)
                if score > best_score and score >= 80:
                    best_score = score
                    best_match = prod

        if best_match:
            return best_match, "fuzzy_name", best_score

    return None, "none", 0.0


@router.post("/catalogue/preview")
async def preview_catalogue_import(
    file: UploadFile = File(...),
    laboratoire_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """
    Preview import catalogue avec rapprochement.

    Retourne un rapport des differences:
    - nouveaux: produits a creer
    - mis_a_jour: produits existants avec changements
    - inchanges: produits existants sans changement
    """
    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == laboratoire_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    try:
        # Lire le fichier
        content = await file.read()
        if file.filename.endswith(".csv"):
            # Essayer plusieurs encodages
            df = None
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding, sep=None, engine="python")
                    break
                except Exception:
                    continue
            if df is None:
                df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))

        # Mapper les colonnes
        column_mapping = {
            "code_cip": ["code_cip", "cip", "code", "CIP", "Code CIP", "CODE CIP", "CIP13", "cip13", "ACL", "EAN", "ean"],
            "designation": ["designation", "nom", "libelle", "produit", "Designation", "DESIGNATION", "Nom", "NOM", "Libelle", "LIBELLE", "Produit", "PRODUIT", "Presentation", "presentation", "PRESENTATION"],
            "prix_ht": ["prix_ht", "prix", "tarif", "Prix HT", "PRIX HT", "Prix", "PRIX", "PPHT", "PU HT", "prix_achat", "Tarif", "TARIF"],
            "remise_pct": ["remise_pct", "remise", "Remise", "REMISE", "% Remise", "% remise", "Remise %", "taux_remise", "Taux Remise"],
        }

        def find_column(dataframe, candidates):
            for col in candidates:
                if col in dataframe.columns:
                    return col
            return None

        mapped_cols = {}
        for target, candidates in column_mapping.items():
            found = find_column(df, candidates)
            if found:
                mapped_cols[target] = found

        # Charger les produits existants du labo
        existing_products = db.query(CatalogueProduit).filter(
            CatalogueProduit.laboratoire_id == laboratoire_id
        ).all()

        # Creer index par CIP pour recherche rapide
        cip_index = {}
        for prod in existing_products:
            if prod.code_cip:
                clean = _clean_cip(prod.code_cip)
                if clean:
                    cip_index[clean] = prod

        # Analyser chaque ligne du fichier
        nouveaux = []
        mis_a_jour = []
        inchanges = []
        erreurs = []

        for idx, row in df.iterrows():
            try:
                # Extraire les donnees
                code_cip = str(row.get(mapped_cols.get("code_cip", ""), "")).strip() if mapped_cols.get("code_cip") else None
                designation = str(row.get(mapped_cols.get("designation", ""), "")).strip() if mapped_cols.get("designation") else None

                # Gerer les valeurs numeriques
                prix_ht_raw = row.get(mapped_cols.get("prix_ht", ""), None) if mapped_cols.get("prix_ht") else None
                remise_pct_raw = row.get(mapped_cols.get("remise_pct", ""), None) if mapped_cols.get("remise_pct") else None

                prix_ht = None
                if prix_ht_raw is not None and pd.notna(prix_ht_raw):
                    try:
                        prix_ht = float(str(prix_ht_raw).replace(",", ".").replace(" ", "").replace("EUR", ""))
                    except Exception:
                        pass

                remise_pct = None
                if remise_pct_raw is not None and pd.notna(remise_pct_raw):
                    try:
                        remise_pct = float(str(remise_pct_raw).replace(",", ".").replace(" ", "").replace("%", ""))
                    except Exception:
                        pass

                # Ignorer les lignes vides
                if not code_cip and not designation:
                    continue

                # Chercher un match
                matched_product, match_type, match_score = _match_product(
                    code_cip, designation, existing_products, cip_index
                )

                ligne_data = {
                    "ligne": idx + 2,  # +2 car header + 0-indexed
                    "code_cip": code_cip,
                    "designation": designation,
                    "prix_ht_import": prix_ht,
                    "remise_pct_import": remise_pct,
                    "match_type": match_type,
                    "match_score": match_score,
                }

                if matched_product:
                    # Produit trouve - verifier les differences
                    ligne_data["produit_id"] = matched_product.id
                    ligne_data["nom_existant"] = matched_product.nom_commercial
                    ligne_data["code_cip_existant"] = matched_product.code_cip
                    ligne_data["prix_ht_existant"] = float(matched_product.prix_ht) if matched_product.prix_ht else None
                    ligne_data["remise_pct_existant"] = float(matched_product.remise_pct) if matched_product.remise_pct else None

                    # Detecter les changements
                    changes = []
                    if prix_ht is not None and matched_product.prix_ht != prix_ht:
                        changes.append({
                            "champ": "prix_ht",
                            "ancien": float(matched_product.prix_ht) if matched_product.prix_ht else None,
                            "nouveau": prix_ht
                        })
                    if remise_pct is not None and matched_product.remise_pct != remise_pct:
                        changes.append({
                            "champ": "remise_pct",
                            "ancien": float(matched_product.remise_pct) if matched_product.remise_pct else None,
                            "nouveau": remise_pct
                        })

                    ligne_data["changes"] = changes

                    if changes:
                        mis_a_jour.append(ligne_data)
                    else:
                        inchanges.append(ligne_data)
                else:
                    # Nouveau produit
                    nouveaux.append(ligne_data)

            except Exception as e:
                erreurs.append({
                    "ligne": idx + 2,
                    "erreur": str(e)
                })

        # Generer un ID unique pour ce preview
        preview_id = hashlib.md5(f"{laboratoire_id}_{file.filename}_{time.time()}".encode()).hexdigest()[:12]

        # Stocker en cache pour confirmation ulterieure
        _import_preview_cache[preview_id] = {
            "laboratoire_id": laboratoire_id,
            "filename": file.filename,
            "nouveaux": nouveaux,
            "mis_a_jour": mis_a_jour,
            "inchanges": inchanges,
            "timestamp": time.time(),
        }

        return {
            "preview_id": preview_id,
            "laboratoire": {
                "id": labo.id,
                "nom": labo.nom,
            },
            "colonnes_detectees": mapped_cols,
            "total_lignes_fichier": len(df),
            "total_produits_existants": len(existing_products),
            "resume": {
                "nouveaux": len(nouveaux),
                "mis_a_jour": len(mis_a_jour),
                "inchanges": len(inchanges),
                "erreurs": len(erreurs),
            },
            "nouveaux": nouveaux[:100],  # Limiter pour la reponse
            "mis_a_jour": mis_a_jour[:100],
            "inchanges": inchanges[:50],
            "erreurs": erreurs[:20],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}")


@router.post("/catalogue/confirm/{preview_id}")
async def confirm_catalogue_import(
    preview_id: str,
    actions: Dict[str, Any] = None,
    db: Session = Depends(get_db)
):
    """
    Confirme et applique l'import apres preview.

    actions peut contenir:
    - apply_nouveaux: bool (defaut True) - creer les nouveaux produits
    - apply_updates: bool (defaut True) - appliquer les mises a jour
    - update_ids: List[int] (optionnel) - IDs specifiques a mettre a jour
    """
    # Recuperer le preview depuis le cache
    if preview_id not in _import_preview_cache:
        raise HTTPException(status_code=404, detail="Preview expire ou introuvable. Veuillez relancer l'import.")

    preview_data = _import_preview_cache[preview_id]

    # Verifier expiration (30 minutes)
    if time.time() - preview_data["timestamp"] > 1800:
        del _import_preview_cache[preview_id]
        raise HTTPException(status_code=410, detail="Preview expire. Veuillez relancer l'import.")

    labo_id = preview_data["laboratoire_id"]

    # Options par defaut
    if actions is None:
        actions = {}
    apply_nouveaux = actions.get("apply_nouveaux", True)
    apply_updates = actions.get("apply_updates", True)
    update_ids = actions.get("update_ids", None)  # None = tous

    nb_crees = 0
    nb_maj = 0

    try:
        # 1. Creer les nouveaux produits
        if apply_nouveaux:
            for item in preview_data["nouveaux"]:
                prix_ht = item.get("prix_ht_import")
                produit = CatalogueProduit(
                    laboratoire_id=labo_id,
                    code_cip=item.get("code_cip"),
                    nom_commercial=item.get("designation"),
                    prix_ht=prix_ht,
                    prix_fabricant=prix_ht,  # Copier prix catalogue
                    prix_source='catalogue' if prix_ht else None,  # Marquer origine
                    remise_pct=item.get("remise_pct_import"),
                    source="manuel",
                )
                db.add(produit)
                nb_crees += 1

        # 2. Appliquer les mises a jour
        if apply_updates:
            for item in preview_data["mis_a_jour"]:
                produit_id = item.get("produit_id")

                # Si update_ids specifie, verifier que ce produit est inclus
                if update_ids is not None and produit_id not in update_ids:
                    continue

                produit = db.query(CatalogueProduit).filter(
                    CatalogueProduit.id == produit_id
                ).first()

                if produit:
                    for change in item.get("changes", []):
                        if change["champ"] == "prix_ht" and change["nouveau"] is not None:
                            produit.prix_ht = change["nouveau"]
                            produit.prix_fabricant = change["nouveau"]  # Maj prix fabricant
                            produit.prix_source = 'catalogue'  # Marquer origine
                        elif change["champ"] == "remise_pct" and change["nouveau"] is not None:
                            produit.remise_pct = change["nouveau"]
                    nb_maj += 1

        db.commit()

        # Nettoyer le cache
        del _import_preview_cache[preview_id]

        return {
            "success": True,
            "laboratoire_id": labo_id,
            "produits_crees": nb_crees,
            "produits_maj": nb_maj,
            "message": f"{nb_crees} produit(s) cree(s), {nb_maj} produit(s) mis a jour"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import: {str(e)}")


@router.delete("/catalogue/preview/{preview_id}")
async def cancel_preview(preview_id: str):
    """Annule un preview en cours."""
    if preview_id in _import_preview_cache:
        del _import_preview_cache[preview_id]
        return {"success": True, "message": "Preview annule"}
    return {"success": False, "message": "Preview non trouve"}
