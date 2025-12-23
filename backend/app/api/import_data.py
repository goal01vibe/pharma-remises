from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import pandas as pd
import io
import time

from app.db import get_db
from app.models import Import, CatalogueProduit, MesVentes, Laboratoire
from app.schemas import ImportResponse, ExtractionPDFResponse, LigneExtraite
from app.services.pdf_extraction import extract_catalogue_from_pdf
from app.services.bdpm_lookup import enrich_ventes_with_bdpm
from app.utils.logger import import_catalogue_logger, import_ventes_logger, OperationMetrics

router = APIRouter(prefix="/api/import", tags=["Import"])


@router.post("/catalogue", response_model=ImportResponse)
async def import_catalogue(
    file: UploadFile = File(...),
    laboratoire_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Importe un catalogue depuis Excel/CSV."""
    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == laboratoire_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Creer l'import
    db_import = Import(
        type_import="catalogue",
        nom_fichier=file.filename,
        laboratoire_id=laboratoire_id,
        statut="en_cours",
    )
    db.add(db_import)
    db.commit()
    db.refresh(db_import)

    try:
        # Lire le fichier
        content = await file.read()
        if file.filename.lower().endswith(".csv"):
            # Auto-detect encoding
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    content_str = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                content_str = content.decode('utf-8', errors='ignore')

            # Auto-detect separator (comma or semicolon)
            first_line = content_str.split('\n')[0]
            separator = ';' if ';' in first_line else ','
            df = pd.read_csv(io.StringIO(content_str), sep=separator, quotechar='"', on_bad_lines='skip')
        else:
            df = pd.read_excel(io.BytesIO(content))

        # Mapper les colonnes (flexible) - variantes francaises et anglaises
        column_mapping = {
            "code_cip": ["code_cip", "cip", "code", "CIP", "Code CIP", "CIP13", "cip13", "EAN", "ean"],
            "designation": ["designation", "nom", "libelle", "produit", "Designation", "Presentation", "presentation", "Nom", "Libelle"],
            "prix_ht": ["prix_ht", "prix", "tarif", "Prix HT", "PPHT", "Tarif", "Prix", "PRIX", "prix_unitaire"],
            "remise_pct": ["remise_pct", "remise", "Remise", "% Remise", "taux_remise", "Taux Remise", "REMISE"],
        }

        def find_column(df, candidates):
            for col in candidates:
                if col in df.columns:
                    return col
            return None

        def parse_float(val):
            """Parse float avec virgule ou point decimal."""
            if val is None or pd.isna(val):
                return None
            val_str = str(val).strip()
            if not val_str:
                return None
            # Remplacer virgule par point pour decimales
            val_str = val_str.replace(',', '.')
            try:
                return float(val_str)
            except ValueError:
                return None

        def parse_percent(val):
            """Parse pourcentage (ex: '30%' -> 30.0 ou '2.5%' -> 2.5)."""
            if val is None or pd.isna(val):
                return None
            val_str = str(val).strip()
            if not val_str:
                return None
            # Enlever le symbole %
            val_str = val_str.replace('%', '').strip()
            # Remplacer virgule par point
            val_str = val_str.replace(',', '.')
            try:
                return float(val_str)
            except ValueError:
                return None

        mapped_cols = {}
        for target, candidates in column_mapping.items():
            found = find_column(df, candidates)
            if found:
                mapped_cols[target] = found

        # === LOGGING: Initialiser les métriques ===
        total_rows = len(df)
        metrics = OperationMetrics(
            import_catalogue_logger,
            "import_catalogue",
            total_items=total_rows,
            batch_size=200  # Log tous les 200 produits
        )
        metrics.start(
            fichier=file.filename,
            laboratoire_id=laboratoire_id,
            labo_nom=labo.nom,
            nb_lignes=total_rows,
            colonnes_detectees=mapped_cols
        )

        nb_imported = 0
        nb_error = 0

        for _, row in df.iterrows():
            try:
                code_cip = str(row.get(mapped_cols.get("code_cip", ""), "")).strip() if mapped_cols.get("code_cip") else None
                designation = str(row.get(mapped_cols.get("designation", ""), "")).strip() if mapped_cols.get("designation") else None
                prix_ht = parse_float(row.get(mapped_cols.get("prix_ht", ""))) if mapped_cols.get("prix_ht") else None
                remise_pct = parse_percent(row.get(mapped_cols.get("remise_pct", ""))) if mapped_cols.get("remise_pct") else None

                if code_cip or designation:
                    produit = CatalogueProduit(
                        laboratoire_id=laboratoire_id,
                        code_cip=code_cip if code_cip else None,
                        nom_commercial=designation if designation else None,
                        prix_ht=prix_ht if prix_ht else None,
                        prix_fabricant=prix_ht if prix_ht else None,  # Copier prix catalogue
                        prix_source='catalogue' if prix_ht else None,  # Marquer origine
                        remise_pct=remise_pct if remise_pct else None,
                        source='manuel',  # Marquer comme import manuel
                    )
                    db.add(produit)
                    nb_imported += 1
                    metrics.increment(success=True)
                else:
                    metrics.increment(success=False)
            except Exception as e:
                nb_error += 1
                metrics.increment(success=False)

        db.commit()

        # Mettre a jour l'import
        db_import.nb_lignes_importees = nb_imported
        db_import.nb_lignes_erreur = nb_error
        db_import.statut = "termine"
        db.commit()
        db.refresh(db_import)

        # === LOGGING: Finaliser les métriques ===
        metrics.finish(
            nb_importes=nb_imported,
            nb_erreurs=nb_error,
            statut="termine"
        )

        return db_import

    except Exception as e:
        db_import.statut = "erreur"
        db.commit()
        import_catalogue_logger.error(f"[ERROR] import_catalogue | fichier: {file.filename} | erreur: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ventes/list", response_model=list[ImportResponse])
def list_ventes_imports(db: Session = Depends(get_db)):
    """Liste tous les imports de ventes."""
    imports = db.query(Import).filter(Import.type_import == "ventes").order_by(Import.created_at.desc()).all()
    return imports


@router.delete("/ventes/cleanup-errors")
def cleanup_errored_imports(db: Session = Depends(get_db)):
    """Supprime tous les imports de ventes en erreur."""
    # Supprimer les imports en erreur
    deleted = db.query(Import).filter(
        Import.type_import == "ventes",
        Import.statut == "erreur"
    ).delete()
    db.commit()
    return {"success": True, "deleted": deleted}


@router.delete("/ventes/{import_id}")
def delete_ventes_import(import_id: int, db: Session = Depends(get_db)):
    """Supprime un import de ventes et toutes ses ventes associees."""
    db_import = db.query(Import).filter(Import.id == import_id, Import.type_import == "ventes").first()
    if not db_import:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Supprimer les ventes associees
    db.query(MesVentes).filter(MesVentes.import_id == import_id).delete()
    db.delete(db_import)
    db.commit()

    return {"success": True, "message": f"Import {import_id} supprime"}


@router.post("/ventes", response_model=ImportResponse)
async def import_ventes(
    file: UploadFile = File(...),
    nom: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Importe les ventes depuis Excel/CSV."""
    # Generer un nom par defaut si non fourni
    import_nom = nom if nom else f"Import {file.filename}"

    db_import = Import(
        type_import="ventes",
        nom=import_nom,
        nom_fichier=file.filename,
        statut="en_cours",
    )
    db.add(db_import)
    db.commit()
    db.refresh(db_import)

    try:
        content = await file.read()
        if file.filename.lower().endswith(".csv"):
            # Auto-detect encoding and separator
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    content_str = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                content_str = content.decode('utf-8', errors='ignore')

            first_line = content_str.split('\n')[0]
            separator = ';' if ';' in first_line else ','
            df = pd.read_csv(io.StringIO(content_str), sep=separator, quotechar='"', on_bad_lines='skip')
        else:
            df = pd.read_excel(io.BytesIO(content))

        # Normaliser les noms de colonnes (lowercase, sans accents, sans espaces)
        import unicodedata
        def normalize_col(col):
            col = str(col).lower().strip()
            col = unicodedata.normalize('NFD', col)
            col = ''.join(c for c in col if unicodedata.category(c) != 'Mn')
            col = col.replace(' ', '_').replace('-', '_')
            return col

        col_map_normalized = {normalize_col(c): c for c in df.columns}

        # Mapping colonnes ventes avec variantes francaises
        column_mapping = {
            "code_cip": ["code_cip", "cip", "code", "codecip", "code_cip13", "cip13", "ean", "ean13"],
            "designation": ["designation", "designation_produit", "nom", "libelle", "produit", "nom_produit", "libelle_produit", "article"],
            "quantite": ["quantite", "qte", "qte_facturee", "quantite_annuelle", "quantite_facturee", "quantite_vendue", "nb", "nombre", "volume"],
            "prix_unitaire": ["prix_unitaire", "prix", "pa", "prix_achat", "pu", "pht", "prix_ht", "prix_unitaire_ht"],
            "labo": ["labo", "laboratoire", "fournisseur", "fabricant", "marque"],
        }

        def find_column(df, candidates):
            # Cherche d'abord dans les colonnes normalisees
            for candidate in candidates:
                norm_candidate = normalize_col(candidate)
                if norm_candidate in col_map_normalized:
                    return col_map_normalized[norm_candidate]
            # Cherche aussi avec correspondance partielle
            for candidate in candidates:
                norm_candidate = normalize_col(candidate)
                for norm_col, orig_col in col_map_normalized.items():
                    if norm_candidate in norm_col or norm_col in norm_candidate:
                        return orig_col
            return None

        mapped_cols = {}
        for target, candidates in column_mapping.items():
            found = find_column(df, candidates)
            if found:
                mapped_cols[target] = found

        # === LOGGING: Initialiser les métriques ===
        total_rows = len(df)
        metrics = OperationMetrics(
            import_ventes_logger,
            "import_ventes",
            total_items=total_rows,
            batch_size=500  # Log tous les 500 ventes
        )
        metrics.start(
            fichier=file.filename,
            nom_import=import_nom,
            nb_lignes=total_rows,
            colonnes_detectees=mapped_cols
        )

        nb_imported = 0
        nb_error = 0
        total_montant = 0

        for _, row in df.iterrows():
            try:
                code_cip = str(row.get(mapped_cols.get("code_cip", ""), "")).strip() if mapped_cols.get("code_cip") else None
                designation = str(row.get(mapped_cols.get("designation", ""), "")).strip() if mapped_cols.get("designation") else None
                quantite = int(row.get(mapped_cols.get("quantite", ""), 0)) if mapped_cols.get("quantite") else None
                prix_unitaire = float(row.get(mapped_cols.get("prix_unitaire", ""), 0)) if mapped_cols.get("prix_unitaire") else None
                labo = str(row.get(mapped_cols.get("labo", ""), "")).strip() if mapped_cols.get("labo") else None

                montant = quantite * prix_unitaire if quantite and prix_unitaire else None

                if code_cip or designation:
                    vente = MesVentes(
                        import_id=db_import.id,
                        code_cip_achete=code_cip if code_cip else None,
                        designation=designation if designation else None,
                        quantite_annuelle=quantite,
                        prix_achat_unitaire=prix_unitaire,
                        montant_annuel=montant,
                        labo_actuel=labo if labo else None,
                    )
                    db.add(vente)
                    nb_imported += 1
                    if montant:
                        total_montant += montant
                    metrics.increment(success=True)
                else:
                    metrics.increment(success=False)
            except Exception:
                nb_error += 1
                metrics.increment(success=False)

        db.commit()

        # === ENRICHISSEMENT BDPM: Ajouter prix BDPM et groupe_generique_id ===
        bdpm_stats = enrich_ventes_with_bdpm(db, db_import.id)
        import_ventes_logger.info(
            f"Enrichissement BDPM: {bdpm_stats['enriched']}/{bdpm_stats['total']} ventes enrichies, "
            f"{bdpm_stats['missing']} sans prix BDPM"
        )

        db_import.nb_lignes_importees = nb_imported
        db_import.nb_lignes_erreur = nb_error
        db_import.statut = "termine"
        db.commit()
        db.refresh(db_import)

        # === LOGGING: Finaliser les métriques ===
        metrics.finish(
            nb_importes=nb_imported,
            nb_erreurs=nb_error,
            montant_total_ht=round(total_montant, 2),
            bdpm_enriched=bdpm_stats['enriched'],
            bdpm_missing=bdpm_stats['missing'],
            statut="termine"
        )

        return db_import

    except Exception as e:
        db_import.statut = "erreur"
        db.commit()
        import_ventes_logger.error(f"[ERROR] import_ventes | fichier: {file.filename} | erreur: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-pdf", response_model=ExtractionPDFResponse)
async def extract_pdf(
    file: UploadFile = File(...),
    page_debut: int = Form(1),
    page_fin: Optional[int] = Form(None),
    modele_ia: str = Form("auto"),
    db: Session = Depends(get_db)
):
    """Extrait les donnees d'un PDF avec IA."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit etre un PDF")

    start_time = time.time()
    content = await file.read()

    result = await extract_catalogue_from_pdf(
        pdf_content=content,
        page_debut=page_debut,
        page_fin=page_fin,
        modele_ia=modele_ia,
    )

    elapsed = time.time() - start_time

    return ExtractionPDFResponse(
        lignes=[LigneExtraite(**l) for l in result["lignes"]],
        nb_pages_traitees=result["nb_pages"],
        modele_utilise=result["modele"],
        temps_extraction_s=round(elapsed, 2),
        raw_response=result.get("raw_response"),
    )


@router.get("/{import_id}", response_model=ImportResponse)
def get_import_status(import_id: int, db: Session = Depends(get_db)):
    """Recupere le statut d'un import."""
    db_import = db.query(Import).filter(Import.id == import_id).first()
    if not db_import:
        raise HTTPException(status_code=404, detail="Import non trouve")
    return db_import


# ============== ENDPOINTS BDPM ==============

from app.services.bdpm_import import import_all_bdpm, import_target_labs, detect_duplicates, get_labo_stats


@router.post("/bdpm/import-all")
async def bdpm_import_all(db: Session = Depends(get_db)):
    """
    Import tous les labos generiques depuis fichiers BDPM.

    Cree les labos qui n'existent pas et enrichit les existants.
    Les produits existants (manuels) ne sont pas ecrases.
    """
    result = import_all_bdpm(db, only_generiques=True)

    return {
        "success": True,
        "labos_crees": result.labos_crees,
        "labos_enrichis": result.labos_enrichis,
        "produits_importes": result.produits_importes,
        "produits_ignores": result.produits_ignores,
        "erreurs": result.erreurs,
        "labos_liste": result.labos_liste[:20],  # Limiter pour la reponse
        "total_labos": len(result.labos_liste)
    }


@router.post("/bdpm/import-target-labs")
async def bdpm_import_target_labs(db: Session = Depends(get_db)):
    """
    Import des 5 labos cibles (BIOGARAN, SANDOZ, ARROW, ZENTIVA, VIATRIS).

    ATTENTION: PURGE la DB et reimporte avec la nouvelle logique:
    - Attribution par pattern de nom (pas titulaire AMM)
    - Generiques seulement (pas de princeps)
    - Produits rembourses seulement
    - Produits commercialises seulement
    """
    result = import_target_labs(db)

    return {
        "success": len(result.erreurs) == 0,
        "labos_crees": result.labos_crees,
        "produits_importes": result.produits_importes,
        "erreurs": result.erreurs,
        "labos_liste": result.labos_liste
    }


@router.get("/bdpm/doublons/{labo_id}")
def bdpm_get_doublons(labo_id: int, db: Session = Depends(get_db)):
    """
    Retourne les doublons potentiels entre produits manuels et BDPM pour un labo.
    """
    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    doublons = detect_duplicates(db, labo_id)

    return {
        "labo_id": labo_id,
        "labo_nom": labo.nom,
        "nb_doublons": len(doublons),
        "doublons": doublons
    }


@router.get("/bdpm/stats")
def bdpm_stats(db: Session = Depends(get_db)):
    """
    Retourne les stats par labo (nb produits total, manuels, bdpm).
    """
    stats = get_labo_stats(db)
    return {
        "total_labos": len(stats),
        "labos": stats
    }


@router.post("/bdpm/mark-manual/{labo_id}")
def bdpm_mark_manual(labo_id: int, db: Session = Depends(get_db)):
    """
    Marque tous les produits existants d'un labo comme 'manuel'.
    Utile pour preparer un labo avant enrichissement BDPM.
    """
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Mettre a jour les produits sans source definie
    updated = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == labo_id,
        (CatalogueProduit.source == None) | (CatalogueProduit.source == 'bdpm')
    ).update({CatalogueProduit.source: 'manuel'}, synchronize_session=False)

    db.commit()

    return {
        "success": True,
        "labo_id": labo_id,
        "labo_nom": labo.nom,
        "produits_marques": updated
    }
# force reload 2024-12-12
# force reload dim. 14 déc. 2025 21:24:47
