"""
Service d'import BDPM - Import des labos generiques et leurs produits depuis les fichiers BDPM.

Fichiers sources (C:\pdf-extractor\data\bdpm\raw\):
- CIS_bdpm.txt : Infos medicaments (CIS, denomination, labo)
- CIS_CIP_bdpm.txt : Presentations (CIS -> CIP13, conditionnement, prix)
- CIS_GENER_bdpm.txt : Groupes generiques (CIS -> groupe_id, type)
"""
import codecs
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.models import Laboratoire, CatalogueProduit

logger = logging.getLogger(__name__)

# Chemin des fichiers BDPM
BDPM_PATH = Path(r"C:\pdf-extractor\data\bdpm\raw")

# =============================================================================
# PATTERNS DE NOMS POUR LES 5 LABOS GENERIQUES CIBLES
# Attribution basée sur le nom commercial du produit, PAS le titulaire AMM BDPM
# Patterns découverts par analyse des catalogues BDPM
# =============================================================================
LAB_PATTERNS = {
    'BIOGARAN': ['BIOGARAN', 'BGR'],  # ALMUS exclu (labo séparé)
    'SANDOZ': ['SANDOZ'],
    'ARROW': ['ARROW'],  # Inclut ARROW LAB, ARROW GENERIQUES automatiquement
    'ZENTIVA': ['ZENTIVA'],  # Inclut ZENTIVA LAB automatiquement
    'VIATRIS': ['VIATRIS', 'MYLAN'],  # VIATRIS a racheté MYLAN - inclut variantes
}

# Liste ordonnée pour la détection (évite conflits de patterns)
TARGET_LABS = ['BIOGARAN', 'SANDOZ', 'ARROW', 'ZENTIVA', 'VIATRIS']


def detect_lab_from_name(denomination: str) -> Optional[str]:
    """
    Détecte le laboratoire cible à partir du nom commercial du produit.

    Args:
        denomination: Nom commercial du produit (ex: "PARACETAMOL BIOGARAN 500mg")

    Returns:
        Nom du labo cible si trouvé, None sinon
    """
    if not denomination:
        return None

    denom_upper = denomination.upper()

    for lab in TARGET_LABS:
        for pattern in LAB_PATTERNS[lab]:
            # Recherche du pattern comme mot entier (pas substring)
            # Ex: "BGR" ne doit pas matcher "BGRIMALDI"
            if re.search(rf'\b{re.escape(pattern)}\b', denom_upper):
                return lab

    return None


@dataclass
class BDPMProduct:
    """Produit extrait des fichiers BDPM."""
    cip13: str
    cis: str
    denomination: str
    labo: str  # Labo attribué par pattern (pas le titulaire AMM)
    labo_amm: Optional[str] = None  # Titulaire AMM original BDPM
    conditionnement: Optional[int] = None
    prix_fabricant: Optional[float] = None
    taux_remboursement: Optional[int] = None  # 0, 15, 30, 65, 100
    groupe_id: Optional[int] = None
    libelle_groupe: Optional[str] = None
    type_generique: Optional[str] = None  # 'princeps', 'generique', 'complementaire'


@dataclass
class ImportResult:
    """Resultat de l'import BDPM."""
    labos_crees: int = 0
    labos_enrichis: int = 0
    produits_importes: int = 0
    produits_ignores: int = 0
    erreurs: List[str] = field(default_factory=list)
    labos_liste: List[str] = field(default_factory=list)


def parse_cis_bdpm(only_commercialises: bool = True) -> Dict[str, Dict]:
    """
    Parse CIS_bdpm.txt pour extraire denomination et laboratoire.

    Structure (12 colonnes, tab-separated):
    Col 1: Code CIS
    Col 2: Denomination
    Col 7: Statut de commercialisation ("Commercialisée" ou "Non commercialisée")
    Col 11: Laboratoire

    Args:
        only_commercialises: Si True, n'inclut que les medicaments "Commercialisée"

    Returns: {cis: {denomination, labo, statut_commercialisation}}
    """
    result = {}
    filepath = BDPM_PATH / "CIS_bdpm.txt"
    total_parses = 0
    non_commercialises = 0

    if not filepath.exists():
        logger.error(f"Fichier non trouve: {filepath}")
        return result

    with codecs.open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 11:
                total_parses += 1
                cis = parts[0].strip()
                denomination = parts[1].strip()
                statut = parts[6].strip() if len(parts) > 6 else ""
                labo = parts[10].strip() if parts[10] else "INCONNU"

                # Filtrer les non commercialisés si demandé
                if only_commercialises and "non commercialis" in statut.lower():
                    non_commercialises += 1
                    continue

                result[cis] = {
                    'denomination': denomination,
                    'labo': labo,
                    'statut_commercialisation': statut
                }

    logger.info(f"CIS_bdpm.txt: {len(result)} medicaments retenus / {total_parses} parses ({non_commercialises} non commercialises exclus)")
    return result


def parse_cis_cip(only_commercialises: bool = True, only_rembourses: bool = False) -> Dict[str, List[Dict]]:
    """
    Parse CIS_CIP_bdpm.txt pour extraire CIP13, conditionnement, prix et remboursement.

    Structure (12-13 colonnes, tab-separated):
    Col 1: Code CIS
    Col 3: Libelle presentation (contient conditionnement)
    Col 5: Statut de commercialisation de la presentation
    Col 7: CIP13
    Col 9: Taux de remboursement (ex: "65%", "100%", "")
    Col 10: Prix fabricant HT

    Args:
        only_commercialises: Si True, n'inclut que les presentations avec
                             "Déclaration de commercialisation" (exclut arrêts)
        only_rembourses: Si True, n'inclut que les produits avec taux > 0%

    Returns: {cis: [{cip13, conditionnement, prix_fabricant, taux_remboursement}]}
    """
    result = {}
    filepath = BDPM_PATH / "CIS_CIP_bdpm.txt"
    total_presentations = 0
    arrets_commercialisation = 0
    non_rembourses = 0

    if not filepath.exists():
        logger.error(f"Fichier non trouve: {filepath}")
        return result

    with codecs.open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 10:
                total_presentations += 1
                cis = parts[0].strip()
                libelle_presentation = parts[2] if len(parts) > 2 else ""
                statut_presentation = parts[4].strip() if len(parts) > 4 else ""
                cip13 = parts[6].strip() if len(parts) > 6 else ""

                # Filtrer les arrêts de commercialisation si demandé
                if only_commercialises and "arr" in statut_presentation.lower():
                    arrets_commercialisation += 1
                    continue

                # Extraire taux de remboursement (col 9, ex: "65%", "100%", "")
                taux_str = parts[8].strip() if len(parts) > 8 else ""
                taux_remboursement = None
                if taux_str and '%' in taux_str:
                    try:
                        taux_remboursement = int(taux_str.replace('%', '').strip())
                    except ValueError:
                        pass

                # Filtrer les non remboursés si demandé
                if only_rembourses and (taux_remboursement is None or taux_remboursement == 0):
                    non_rembourses += 1
                    continue

                # Prix fabricant (col 10)
                prix_str = parts[9].strip() if len(parts) > 9 else ""
                prix_fabricant = None
                if prix_str:
                    try:
                        if prix_str.count(',') >= 2:
                            parts_prix = prix_str.rsplit(',', 1)
                            prix_str_clean = parts_prix[0].replace(',', '') + '.' + parts_prix[1]
                        else:
                            prix_str_clean = prix_str.replace(',', '.')
                        prix_fabricant = float(prix_str_clean)
                    except ValueError:
                        pass

                # Extraire conditionnement du libelle
                conditionnement = extract_conditionnement(libelle_presentation)

                if cis and cip13:
                    if cis not in result:
                        result[cis] = []
                    result[cis].append({
                        'cip13': cip13,
                        'conditionnement': conditionnement,
                        'prix_fabricant': prix_fabricant,
                        'taux_remboursement': taux_remboursement,
                        'libelle': libelle_presentation
                    })

    logger.info(f"CIS_CIP_bdpm.txt: {len(result)} CIS retenus / {total_presentations} presentations ({arrets_commercialisation} arrets, {non_rembourses} non rembourses exclus)")
    return result


def extract_conditionnement(libelle: str) -> Optional[int]:
    """
    Extrait le conditionnement d'un libelle de presentation.

    Exemples:
    - "plaquette(s) PVC de 30 comprimé(s)" -> 30
    - "90 gélule(s)" -> 90
    - "flacon de 100 ml" -> 100
    """
    if not libelle:
        return None

    # Patterns pour conditionnements courants
    patterns = [
        r'de\s+(\d+)\s+(?:comprim|gelule|capsule|sachet|dose|ampoule)',
        r'(\d+)\s+(?:comprim|gelule|capsule|sachet|dose|ampoule)',
        r'(\d+)\s+(?:unidose|recipient)',
        r'(?:bt|boite|bte)\s*(?:de\s*)?(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, libelle.lower())
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    return None


def parse_cis_gener() -> Dict[str, Dict]:
    """
    Parse CIS_GENER_bdpm.txt pour extraire les groupes generiques.

    Structure (5 colonnes, tab-separated):
    Col 1: ID groupe generique
    Col 2: Libelle groupe
    Col 3: Code CIS
    Col 4: Type (0=princeps, 1=generique, 2=complementaire)
    Col 5: Numero tri

    Returns: {cis: {groupe_id, libelle, type}}
    """
    result = {}
    filepath = BDPM_PATH / "CIS_GENER_bdpm.txt"

    if not filepath.exists():
        logger.error(f"Fichier non trouve: {filepath}")
        return result

    type_map = {
        '0': 'princeps',
        '1': 'generique',
        '2': 'complementaire'
    }

    with codecs.open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                try:
                    groupe_id = int(parts[0].strip())
                except ValueError:
                    continue

                libelle = parts[1].strip()
                cis = parts[2].strip()
                type_code = parts[3].strip()

                result[cis] = {
                    'groupe_id': groupe_id,
                    'libelle': libelle,
                    'type': type_map.get(type_code, 'inconnu')
                }

    logger.info(f"CIS_GENER_bdpm.txt: {len(result)} CIS avec groupe generique")
    return result


def get_generiques_labos(cis_bdpm: Dict, cis_gener: Dict) -> set:
    """
    Retourne l'ensemble des labos qui ont au moins un produit generique (type=1 ou 2).
    EXCLUT les labos qui n'ont que des princeps (type=0).
    """
    labos = set()
    for cis, gener_data in cis_gener.items():
        # Seulement generiques (type=1) et complementaires (type=2), PAS princeps (type=0)
        if gener_data['type'] in ('generique', 'complementaire'):
            if cis in cis_bdpm:
                labos.add(cis_bdpm[cis]['labo'])
    return labos


def build_products_list(cis_bdpm: Dict, cis_cip: Dict, cis_gener: Dict, only_generiques: bool = True) -> List[BDPMProduct]:
    """
    Construit la liste des produits a importer en croisant les 3 fichiers.

    Args:
        only_generiques: Si True, n'importe que les VRAIS generiques (type=1,2), EXCLUT les princeps (type=0)
    """
    products = []

    for cis, presentations in cis_cip.items():
        if cis not in cis_bdpm:
            continue

        bdpm_data = cis_bdpm[cis]
        labo = bdpm_data['labo']

        # Filtrer si seulement generiques
        if only_generiques:
            # Le produit DOIT etre dans CIS_GENER
            if cis not in cis_gener:
                continue

            gener_data = cis_gener[cis]

            # EXCLURE les princeps (type=0) - on ne garde que generiques (1) et complementaires (2)
            if gener_data['type'] == 'princeps':
                continue
        else:
            gener_data = cis_gener.get(cis, {})

        for pres in presentations:
            product = BDPMProduct(
                cip13=pres['cip13'],
                cis=cis,
                denomination=bdpm_data['denomination'],
                labo=labo,
                conditionnement=pres['conditionnement'],
                prix_fabricant=pres['prix_fabricant'],
                groupe_id=gener_data.get('groupe_id'),
                libelle_groupe=gener_data.get('libelle'),
                type_generique=gener_data.get('type')
            )
            products.append(product)

    logger.info(f"Total produits a importer: {len(products)}")
    return products


def import_all_bdpm(db: Session, only_generiques: bool = True) -> ImportResult:
    """
    Import complet de tous les labos generiques depuis BDPM.

    Args:
        db: Session SQLAlchemy
        only_generiques: Si True, n'importe que les labos generiqueurs

    Returns:
        ImportResult avec stats
    """
    result = ImportResult()

    logger.info("=== DEBUT IMPORT BDPM ===")

    # 1. Parser les fichiers
    logger.info("Parsing CIS_bdpm.txt...")
    cis_bdpm = parse_cis_bdpm()

    logger.info("Parsing CIS_CIP_bdpm.txt...")
    cis_cip = parse_cis_cip()

    logger.info("Parsing CIS_GENER_bdpm.txt...")
    cis_gener = parse_cis_gener()

    if not cis_bdpm or not cis_cip:
        result.erreurs.append("Fichiers BDPM manquants ou vides")
        return result

    # 2. Construire la liste des produits
    products = build_products_list(cis_bdpm, cis_cip, cis_gener, only_generiques)

    # 3. Grouper par labo
    products_by_labo = {}
    for p in products:
        if p.labo not in products_by_labo:
            products_by_labo[p.labo] = []
        products_by_labo[p.labo].append(p)

    logger.info(f"Labos a traiter: {len(products_by_labo)}")

    # 4. Importer chaque labo (commit par labo pour eviter les erreurs en cascade)
    for labo_name, labo_products in products_by_labo.items():
        try:
            # Verifier si le labo existe
            labo = db.query(Laboratoire).filter(Laboratoire.nom == labo_name).first()

            if labo:
                # Labo existant -> enrichir (ne pas ecraser les manuels)
                result.labos_enrichis += 1
                imported, ignored = _enrich_labo(db, labo, labo_products)
            else:
                # Nouveau labo -> creer
                labo = Laboratoire(
                    nom=labo_name,
                    actif=True
                )
                db.add(labo)
                db.flush()  # Pour obtenir l'ID
                result.labos_crees += 1
                imported, ignored = _import_labo_products(db, labo, labo_products)

            # Commit par labo pour isoler les erreurs
            db.commit()

            result.produits_importes += imported
            result.produits_ignores += ignored
            result.labos_liste.append(labo_name)

        except Exception as e:
            db.rollback()  # Rollback pour ce labo uniquement
            result.erreurs.append(f"Erreur labo {labo_name}: {str(e)[:100]}")
            logger.error(f"Erreur import labo {labo_name}: {e}")

    logger.info(f"=== FIN IMPORT BDPM ===")
    logger.info(f"Labos crees: {result.labos_crees}, enrichis: {result.labos_enrichis}")
    logger.info(f"Produits importes: {result.produits_importes}, ignores: {result.produits_ignores}")

    return result


def _truncate(value: str, max_len: int) -> str:
    """Tronque une chaine si trop longue."""
    if value and len(value) > max_len:
        return value[:max_len-3] + "..."
    return value


def _import_labo_products(db: Session, labo: Laboratoire, products: List[BDPMProduct]) -> Tuple[int, int]:
    """
    Importe les produits d'un nouveau labo.

    Returns: (imported_count, ignored_count)
    """
    imported = 0
    ignored = 0

    for p in products:
        try:
            produit = CatalogueProduit(
                laboratoire_id=labo.id,
                code_cip=p.cip13,
                code_cis=p.cis,
                nom_commercial=_truncate(p.denomination, 200),
                prix_fabricant=p.prix_fabricant,
                conditionnement=p.conditionnement,
                groupe_generique_id=p.groupe_id,
                libelle_groupe=_truncate(p.libelle_groupe, 300) if p.libelle_groupe else None,
                type_generique=p.type_generique,
                source='bdpm',
                actif=True
            )
            db.add(produit)
            imported += 1
        except Exception as e:
            logger.warning(f"Erreur produit {p.cip13}: {e}")
            ignored += 1

    return imported, ignored


def _enrich_labo(db: Session, labo: Laboratoire, products: List[BDPMProduct]) -> Tuple[int, int]:
    """
    Enrichit un labo existant avec les produits BDPM manquants.
    Ne touche pas aux produits manuels existants.

    Returns: (imported_count, ignored_count)
    """
    imported = 0
    ignored = 0

    # Recuperer les CIP existants pour ce labo
    existing_cips = set(
        row[0] for row in db.query(CatalogueProduit.code_cip)
        .filter(CatalogueProduit.laboratoire_id == labo.id)
        .all()
        if row[0]
    )

    for p in products:
        if p.cip13 in existing_cips:
            # Produit existe deja -> ignorer
            ignored += 1
            continue

        try:
            produit = CatalogueProduit(
                laboratoire_id=labo.id,
                code_cip=p.cip13,
                code_cis=p.cis,
                nom_commercial=_truncate(p.denomination, 200),
                prix_fabricant=p.prix_fabricant,
                conditionnement=p.conditionnement,
                groupe_generique_id=p.groupe_id,
                libelle_groupe=_truncate(p.libelle_groupe, 300) if p.libelle_groupe else None,
                type_generique=p.type_generique,
                source='bdpm',
                actif=True
            )
            db.add(produit)
            imported += 1
        except Exception as e:
            logger.warning(f"Erreur produit {p.cip13}: {e}")
            ignored += 1

    return imported, ignored


def detect_duplicates(db: Session, labo_id: int) -> List[Dict]:
    """
    Detecte les doublons potentiels entre produits manuels et BDPM pour un labo.

    Returns: Liste des doublons avec infos comparatives
    """
    # Produits manuels
    manuels = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == labo_id,
        CatalogueProduit.source == 'manuel'
    ).all()

    # Produits BDPM
    bdpm_products = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == labo_id,
        CatalogueProduit.source == 'bdpm'
    ).all()

    doublons = []

    for manuel in manuels:
        for bdpm in bdpm_products:
            # Match par CIP exact
            if manuel.code_cip and bdpm.code_cip and manuel.code_cip == bdpm.code_cip:
                doublons.append({
                    'type': 'cip_exact',
                    'manuel_id': manuel.id,
                    'manuel_cip': manuel.code_cip,
                    'manuel_nom': manuel.nom_commercial,
                    'bdpm_id': bdpm.id,
                    'bdpm_cip': bdpm.code_cip,
                    'bdpm_nom': bdpm.nom_commercial,
                    'recommendation': 'Supprimer le manuel (CIP identique)'
                })
            # Match par nom similaire (a affiner)
            elif manuel.nom_commercial and bdpm.nom_commercial:
                if _similar_names(manuel.nom_commercial, bdpm.nom_commercial):
                    doublons.append({
                        'type': 'nom_similaire',
                        'manuel_id': manuel.id,
                        'manuel_cip': manuel.code_cip,
                        'manuel_nom': manuel.nom_commercial,
                        'bdpm_id': bdpm.id,
                        'bdpm_cip': bdpm.code_cip,
                        'bdpm_nom': bdpm.nom_commercial,
                        'recommendation': 'Verifier manuellement'
                    })

    return doublons


def _similar_names(name1: str, name2: str) -> bool:
    """
    Verifie si deux noms de produits sont similaires.
    Simplifie: compare les premiers mots (molecule).
    """
    if not name1 or not name2:
        return False

    # Normaliser
    n1 = name1.upper().split()[0] if name1.split() else ""
    n2 = name2.upper().split()[0] if name2.split() else ""

    return n1 and n2 and n1 == n2


def get_labo_stats(db: Session) -> List[Dict]:
    """
    Retourne les stats par labo (nb produits, nb manuels, nb bdpm).
    """
    from sqlalchemy import func, case

    stats = db.query(
        Laboratoire.id,
        Laboratoire.nom,
        func.count(CatalogueProduit.id).label('total'),
        func.sum(case((CatalogueProduit.source == 'manuel', 1), else_=0)).label('manuels'),
        func.sum(case((CatalogueProduit.source == 'bdpm', 1), else_=0)).label('bdpm')
    ).outerjoin(CatalogueProduit).group_by(Laboratoire.id, Laboratoire.nom).all()

    return [
        {
            'id': s.id,
            'nom': s.nom,
            'total': s.total or 0,
            'manuels': int(s.manuels or 0),
            'bdpm': int(s.bdpm or 0)
        }
        for s in stats
    ]


# =============================================================================
# NOUVELLE FONCTION : Import des 5 labos cibles avec attribution par pattern
# =============================================================================

def build_products_for_target_labs(
    cis_bdpm: Dict,
    cis_cip: Dict,
    cis_gener: Dict
) -> Dict[str, List[BDPMProduct]]:
    """
    Construit la liste des produits pour les 5 labos cibles UNIQUEMENT.

    Attribution basée sur le NOM du produit (patterns), pas le titulaire AMM.
    Filtre: génériques seulement (pas de princeps).

    Returns: {lab_name: [BDPMProduct, ...]}
    """
    products_by_lab = {lab: [] for lab in TARGET_LABS}
    stats = {
        'total_cis': 0,
        'no_pattern_match': 0,
        'princeps_excluded': 0,
        'not_in_gener': 0,
    }

    for cis, presentations in cis_cip.items():
        if cis not in cis_bdpm:
            continue

        stats['total_cis'] += 1
        bdpm_data = cis_bdpm[cis]
        denomination = bdpm_data['denomination']
        labo_amm = bdpm_data['labo']

        # Détecter le labo cible par le nom du produit
        target_lab = detect_lab_from_name(denomination)
        if not target_lab:
            stats['no_pattern_match'] += 1
            continue

        # Vérifier que c'est un générique (pas princeps)
        if cis not in cis_gener:
            stats['not_in_gener'] += 1
            continue

        gener_data = cis_gener[cis]
        if gener_data['type'] == 'princeps':
            stats['princeps_excluded'] += 1
            continue

        # Créer les produits pour chaque présentation
        for pres in presentations:
            product = BDPMProduct(
                cip13=pres['cip13'],
                cis=cis,
                denomination=denomination,
                labo=target_lab,  # Attribution par pattern!
                labo_amm=labo_amm,
                conditionnement=pres['conditionnement'],
                prix_fabricant=pres['prix_fabricant'],
                taux_remboursement=pres.get('taux_remboursement'),
                groupe_id=gener_data.get('groupe_id'),
                libelle_groupe=gener_data.get('libelle'),
                type_generique=gener_data.get('type')
            )
            products_by_lab[target_lab].append(product)

    # Log stats
    logger.info(f"Build products for target labs:")
    logger.info(f"  - Total CIS parsés: {stats['total_cis']}")
    logger.info(f"  - Sans pattern match: {stats['no_pattern_match']}")
    logger.info(f"  - Pas dans CIS_GENER: {stats['not_in_gener']}")
    logger.info(f"  - Princeps exclus: {stats['princeps_excluded']}")
    for lab in TARGET_LABS:
        logger.info(f"  - {lab}: {len(products_by_lab[lab])} produits")

    return products_by_lab


def import_target_labs(db: Session) -> ImportResult:
    """
    Import COMPLET des 5 labos cibles avec la nouvelle logique:
    - Attribution par pattern de nom (pas titulaire AMM)
    - Génériques seulement (pas de princeps)
    - Produits remboursés seulement
    - Produits commercialisés seulement

    ATTENTION: Cette fonction PURGE les labos existants avant import!
    """
    result = ImportResult()

    logger.info("=" * 60)
    logger.info("IMPORT 5 LABOS CIBLES - NOUVELLE LOGIQUE")
    logger.info("=" * 60)

    # 1. Parser les fichiers avec filtres
    logger.info("Parsing CIS_bdpm.txt (commercialisés seulement)...")
    cis_bdpm = parse_cis_bdpm(only_commercialises=True)

    logger.info("Parsing CIS_CIP_bdpm.txt (commercialisés + remboursés)...")
    cis_cip = parse_cis_cip(only_commercialises=True, only_rembourses=True)

    logger.info("Parsing CIS_GENER_bdpm.txt...")
    cis_gener = parse_cis_gener()

    if not cis_bdpm or not cis_cip:
        result.erreurs.append("Fichiers BDPM manquants ou vides")
        return result

    # 2. Construire les produits par labo cible
    products_by_lab = build_products_for_target_labs(cis_bdpm, cis_cip, cis_gener)

    # 3. Purger les anciens labos et produits
    logger.info("Purge des anciens labos et produits...")
    deleted_products = db.query(CatalogueProduit).delete()
    deleted_labos = db.query(Laboratoire).delete()
    db.commit()
    logger.info(f"  - {deleted_products} produits supprimés")
    logger.info(f"  - {deleted_labos} labos supprimés")

    # 4. Créer les 5 labos cibles et leurs produits
    for lab_name in TARGET_LABS:
        lab_products = products_by_lab[lab_name]

        if not lab_products:
            logger.warning(f"Aucun produit pour {lab_name}, labo non créé")
            continue

        try:
            # Créer le labo
            labo = Laboratoire(nom=lab_name, actif=True)
            db.add(labo)
            db.flush()
            result.labos_crees += 1

            # Ajouter les produits
            for p in lab_products:
                produit = CatalogueProduit(
                    laboratoire_id=labo.id,
                    code_cip=p.cip13,
                    code_cis=p.cis,
                    nom_commercial=_truncate(p.denomination, 200),
                    prix_fabricant=p.prix_fabricant,
                    conditionnement=p.conditionnement,
                    groupe_generique_id=p.groupe_id,
                    libelle_groupe=_truncate(p.libelle_groupe, 300) if p.libelle_groupe else None,
                    type_generique=p.type_generique,
                    source='bdpm',
                    actif=True
                )
                db.add(produit)
                result.produits_importes += 1

            db.commit()
            result.labos_liste.append(lab_name)
            logger.info(f"  ✓ {lab_name}: {len(lab_products)} produits importés")

        except Exception as e:
            db.rollback()
            result.erreurs.append(f"Erreur labo {lab_name}: {str(e)[:100]}")
            logger.error(f"Erreur import labo {lab_name}: {e}")

    logger.info("=" * 60)
    logger.info(f"IMPORT TERMINE: {result.labos_crees} labos, {result.produits_importes} produits")
    logger.info("=" * 60)

    return result
