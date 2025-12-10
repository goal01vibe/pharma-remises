import re
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Presentation, CatalogueProduit


def extract_molecule_dosage(designation: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrait la molecule et le dosage d'une designation.

    Exemples:
        "Furosemide Viatris 40mg Cpr B/30" -> ("Furosemide", "40mg")
        "OMEPRAZOLE ZENTIVA 20 mg Gel" -> ("Omeprazole", "20mg")
    """
    # Nettoyer
    text = designation.strip()

    # Pattern pour extraire le dosage (ex: 40mg, 20 mg, 500mg/5ml)
    dosage_pattern = r'(\d+(?:,\d+)?(?:\s*mg|\s*g|\s*ml|\s*µg|mg/ml|mg/\d+ml))'
    dosage_match = re.search(dosage_pattern, text, re.IGNORECASE)
    dosage = dosage_match.group(1).replace(" ", "") if dosage_match else None

    # Le premier mot est souvent la molecule
    # On enleve les noms de labos connus
    labos = ["viatris", "zentiva", "biogaran", "sandoz", "teva", "mylan", "arrow", "eg", "cristers"]
    words = text.split()
    molecule = None

    for word in words:
        word_clean = word.lower().strip(",").strip(".")
        if word_clean not in labos and len(word_clean) > 2 and not re.match(r'^\d', word_clean):
            molecule = word_clean.capitalize()
            break

    return molecule, dosage


def classify_conditionnement(qty: int) -> str:
    """Classifie un conditionnement en petit ou grand."""
    # Seuil par defaut: 60
    return "grand" if qty >= 60 else "petit"


def generate_code_interne(molecule: str, dosage: str, conditionnement: int) -> str:
    """Genere un code interne standardise."""
    # Ex: FURO-40MG-30
    mol_prefix = molecule[:4].upper() if molecule else "UNKN"
    dos = dosage.replace(" ", "").upper() if dosage else ""
    cond = str(conditionnement) if conditionnement else ""

    return f"{mol_prefix}-{dos}-{cond}"


def auto_match_product(
    db: Session,
    designation: str,
    conditionnement: Optional[int] = None
) -> Tuple[Optional[Presentation], str]:
    """
    Tente de matcher automatiquement un produit avec une presentation.

    Returns:
        Tuple[presentation, status] ou status est 'auto', 'ambiguous', 'new'
    """
    molecule, dosage = extract_molecule_dosage(designation)

    if not molecule:
        return None, "new"

    # Rechercher des presentations candidates
    candidates = find_presentation_candidates(db, molecule, dosage, conditionnement)

    if len(candidates) == 1:
        return candidates[0], "auto"
    elif len(candidates) > 1:
        return candidates[0], "ambiguous"  # Retourne le premier mais signale l'ambiguite
    else:
        return None, "new"


def find_presentation_candidates(
    db: Session,
    molecule: str,
    dosage: Optional[str] = None,
    conditionnement: Optional[int] = None
) -> List[Presentation]:
    """
    Recherche les presentations candidates pour un matching.
    """
    query = db.query(Presentation)

    # Recherche sur la molecule (fuzzy)
    query = query.filter(Presentation.molecule.ilike(f"%{molecule}%"))

    # Filtrer par dosage si disponible
    if dosage:
        # Normaliser le dosage (enlever espaces)
        dosage_norm = dosage.replace(" ", "").lower()
        query = query.filter(
            or_(
                Presentation.dosage.ilike(f"%{dosage}%"),
                Presentation.dosage.ilike(f"%{dosage_norm}%"),
            )
        )

    # Filtrer par type de conditionnement si disponible
    if conditionnement:
        type_cond = classify_conditionnement(conditionnement)
        query = query.filter(Presentation.type_conditionnement == type_cond)

    return query.limit(10).all()


def create_presentation_from_product(
    molecule: str,
    dosage: Optional[str],
    conditionnement: Optional[int],
    forme: Optional[str] = None
) -> dict:
    """
    Cree les donnees pour une nouvelle presentation.
    """
    type_cond = classify_conditionnement(conditionnement) if conditionnement else None
    code_interne = generate_code_interne(molecule, dosage or "", conditionnement or 0)

    return {
        "code_interne": code_interne,
        "molecule": molecule,
        "dosage": dosage,
        "forme": forme,
        "conditionnement": conditionnement,
        "type_conditionnement": type_cond,
    }
