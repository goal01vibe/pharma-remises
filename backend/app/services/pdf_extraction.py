import os
import json
import re
import io
import logging
from typing import Dict, Any, Optional, List
import pdfplumber
from openai import AsyncOpenAI

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Client OpenAI - sera initialisé à la première utilisation
_client: Optional[AsyncOpenAI] = None

def get_openai_client() -> AsyncOpenAI:
    """Récupère ou crée le client OpenAI."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        logger.info(f"OPENAI_API_KEY present: {bool(api_key and api_key != 'your_openai_api_key_here')}")
        if not api_key or api_key == "your_openai_api_key_here":
            raise ValueError("OPENAI_API_KEY non configurée. Ajoutez votre clé API dans le fichier .env")
        _client = AsyncOpenAI(api_key=api_key)
        logger.info("Client OpenAI initialisé avec succès")
    return _client

EXTRACTION_PROMPT = """Tu es un expert en extraction de donnees de catalogues pharmaceutiques.

Extrait les donnees du tableau de catalogue ci-dessous.
Pour chaque ligne de produit, retourne un objet JSON avec:
- code_cip: Code CIP/ACL (13 chiffres, peut commencer par 340093...)
- designation: Nom complet du produit
- prix_ht: Prix HT (nombre decimal, ex: 4.50)
- remise_pct: Pourcentage de remise (nombre, ex: 35)

Regles:
- Ignore les lignes d'en-tete et les lignes vides
- Si une valeur est manquante, mets null
- Le code CIP fait generalement 13 chiffres
- Le prix peut etre en format 4,50 ou 4.50
- La remise peut etre notee 35% ou 35 ou 0.35

Retourne UNIQUEMENT un JSON array valide, sans texte additionnel.

Exemple de sortie:
[
  {"code_cip": "3400936000001", "designation": "Furosemide 40mg B/30", "prix_ht": 4.50, "remise_pct": 35},
  {"code_cip": "3400936000002", "designation": "Omeprazole 20mg B/28", "prix_ht": 3.20, "remise_pct": 40}
]

Texte a analyser:
"""


async def extract_catalogue_from_pdf(
    pdf_content: bytes,
    page_debut: int = 1,
    page_fin: Optional[int] = None,
    modele_ia: str = "auto"
) -> Dict[str, Any]:
    """
    Extrait les donnees d'un catalogue PDF avec IA.
    Découpe automatiquement en lots de 5 pages pour éviter les limites de tokens.

    Args:
        pdf_content: Contenu binaire du PDF
        page_debut: Page de debut (1-indexed)
        page_fin: Page de fin (incluse)
        modele_ia: 'auto', 'gpt-4o-mini', ou 'gpt-4o'

    Returns:
        Dict avec lignes extraites, nb_pages, et modele utilise
    """
    PAGES_PAR_LOT = 5  # Nombre de pages par appel IA

    logger.info(f"=== DEBUT EXTRACTION PDF ===")
    logger.info(f"Pages: {page_debut} à {page_fin}, Modèle: {modele_ia}")

    # Convertir bytes en file-like object et extraire texte par page
    pdf_file = io.BytesIO(pdf_content)
    pages_text = []  # Liste de tuples (page_num, text)

    with pdfplumber.open(pdf_file) as pdf:
        total_pages = len(pdf.pages)
        end_page = min(page_fin or total_pages, total_pages)
        logger.info(f"PDF: {total_pages} pages totales, extraction de {page_debut} à {end_page}")

        for i in range(page_debut - 1, end_page):
            page = pdf.pages[i]
            text = page.extract_text() or ""
            pages_text.append((i + 1, text))

    nb_pages = len(pages_text)
    logger.info(f"Texte extrait de {nb_pages} pages")

    if not pages_text:
        logger.warning("AUCUN TEXTE EXTRAIT DU PDF!")
        return {"lignes": [], "nb_pages": 0, "modele": modele_ia, "raw_response": ""}

    # Determiner le modele a utiliser
    if modele_ia == "auto":
        model = "gpt-4o-mini"
    else:
        model = modele_ia

    # Découper en lots et extraire
    all_lignes = []
    all_raw_responses = []
    nb_lots = (nb_pages + PAGES_PAR_LOT - 1) // PAGES_PAR_LOT

    logger.info(f"Extraction en {nb_lots} lot(s) de {PAGES_PAR_LOT} pages max")

    for lot_idx in range(nb_lots):
        start_idx = lot_idx * PAGES_PAR_LOT
        end_idx = min(start_idx + PAGES_PAR_LOT, nb_pages)
        lot_pages = pages_text[start_idx:end_idx]

        # Construire le texte du lot
        lot_text = ""
        for page_num, text in lot_pages:
            lot_text += f"\n--- Page {page_num} ---\n{text}"

        logger.info(f"Lot {lot_idx + 1}/{nb_lots}: pages {lot_pages[0][0]}-{lot_pages[-1][0]}, {len(lot_text)} caractères")

        # Appeler l'API OpenAI pour ce lot
        lignes, raw_response = await call_openai_extraction(lot_text, model)
        logger.info(f"Lot {lot_idx + 1}: {len(lignes)} lignes extraites")

        # Si échec avec gpt-4o-mini en mode auto, retry avec gpt-4o
        if modele_ia == "auto" and len(lignes) == 0 and model == "gpt-4o-mini":
            logger.info(f"Lot {lot_idx + 1}: retry avec gpt-4o")
            lignes, raw_response = await call_openai_extraction(lot_text, "gpt-4o")
            if lignes:
                model = "gpt-4o"  # Switcher pour les lots suivants aussi
            logger.info(f"Lot {lot_idx + 1} (retry gpt-4o): {len(lignes)} lignes extraites")

        all_lignes.extend(lignes)
        all_raw_responses.append(f"=== LOT {lot_idx + 1} (pages {lot_pages[0][0]}-{lot_pages[-1][0]}) ===\n{raw_response}")

    logger.info(f"=== FIN EXTRACTION PDF: {len(all_lignes)} lignes totales ===")

    return {
        "lignes": all_lignes,
        "nb_pages": nb_pages,
        "modele": model,
        "raw_response": "\n\n".join(all_raw_responses),
    }


async def call_openai_extraction(text: str, model: str) -> tuple[List[Dict[str, Any]], str]:
    """Appelle l'API OpenAI pour extraire les donnees.

    Returns:
        Tuple (lignes extraites, réponse brute de l'IA)
    """
    client = get_openai_client()
    raw_response = ""

    try:
        logger.info(f"Appel OpenAI avec modèle {model}...")
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en extraction de donnees. Reponds uniquement en JSON valide."
                },
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT + text[:120000]  # ~30K tokens en entrée, suffisant pour 30+ pages
                }
            ],
            temperature=0.1,
            max_tokens=16384,  # Maximum pour gpt-4o-mini (16K output)
        )

        raw_response = response.choices[0].message.content.strip()
        logger.info(f"Réponse OpenAI reçue: {len(raw_response)} caractères")
        logger.info(f"Réponse brute (500 premiers chars): {raw_response[:500]}")

        content = raw_response

        # Nettoyer la reponse (enlever les backticks markdown si presents)
        if content.startswith("```"):
            content = re.sub(r"^```json?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        # Parser le JSON
        lignes = json.loads(content)
        logger.info(f"JSON parsé avec succès: {len(lignes)} lignes")

        # Ajouter un score de confiance basique
        for ligne in lignes:
            confiance = 1.0
            if not ligne.get("code_cip"):
                confiance -= 0.3
            if not ligne.get("designation"):
                confiance -= 0.3
            if ligne.get("prix_ht") is None:
                confiance -= 0.2
            ligne["confiance"] = max(0, confiance)

        return lignes, raw_response

    except json.JSONDecodeError as e:
        logger.error(f"ERREUR JSON: {e}")
        logger.error(f"Contenu qui a échoué: {raw_response[:1000]}")
        return [], raw_response
    except Exception as e:
        logger.error(f"ERREUR extraction OpenAI: {type(e).__name__}: {e}")
        return [], f"ERREUR: {type(e).__name__}: {e}"
