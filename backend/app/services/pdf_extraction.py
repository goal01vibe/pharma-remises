import os
import json
import re
from typing import Dict, Any, Optional, List
import pdfplumber
from openai import AsyncOpenAI

# Client OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

    Args:
        pdf_content: Contenu binaire du PDF
        page_debut: Page de debut (1-indexed)
        page_fin: Page de fin (incluse)
        modele_ia: 'auto', 'gpt-4o-mini', ou 'gpt-4o'

    Returns:
        Dict avec lignes extraites, nb_pages, et modele utilise
    """
    # Extraire le texte des pages
    all_text = ""
    nb_pages = 0

    with pdfplumber.open_file_like(pdf_content) as pdf:
        total_pages = len(pdf.pages)
        end_page = min(page_fin or total_pages, total_pages)

        for i in range(page_debut - 1, end_page):
            page = pdf.pages[i]
            text = page.extract_text() or ""
            all_text += f"\n--- Page {i + 1} ---\n{text}"
            nb_pages += 1

    # Determiner le modele a utiliser
    if modele_ia == "auto":
        model = "gpt-4o-mini"  # Commencer par le moins cher
    else:
        model = modele_ia

    # Appeler l'API OpenAI
    lignes = await call_openai_extraction(all_text, model)

    # Si auto et peu de resultats ou confiance basse, retry avec gpt-4o
    if modele_ia == "auto" and len(lignes) < 5:
        model = "gpt-4o"
        lignes = await call_openai_extraction(all_text, model)

    return {
        "lignes": lignes,
        "nb_pages": nb_pages,
        "modele": model,
    }


async def call_openai_extraction(text: str, model: str) -> List[Dict[str, Any]]:
    """Appelle l'API OpenAI pour extraire les donnees."""
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en extraction de donnees. Reponds uniquement en JSON valide."
                },
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT + text[:50000]  # Limite de caracteres
                }
            ],
            temperature=0.1,
            max_tokens=4000,
        )

        content = response.choices[0].message.content.strip()

        # Nettoyer la reponse (enlever les backticks markdown si presents)
        if content.startswith("```"):
            content = re.sub(r"^```json?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        # Parser le JSON
        lignes = json.loads(content)

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

        return lignes

    except json.JSONDecodeError:
        # Si le JSON est invalide, retourner une liste vide
        return []
    except Exception as e:
        print(f"Erreur extraction OpenAI: {e}")
        return []
