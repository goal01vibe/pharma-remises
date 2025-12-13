"""
Script pour mettre a jour les prix fabricant (PFHT) dans les catalogues labos.

Met a jour UNIQUEMENT les produits existants dans catalogue_produits
avec les prix PFHT de la BDPM.

Usage:
    cd C:/pharma-remises/backend
    python -m app.scripts.update_pfht_catalogues
"""
import sys
from pathlib import Path
from decimal import Decimal

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.db.database import SessionLocal

# Chemin du fichier BDPM
BDPM_DIR = Path(r"C:\pdf-extractor\data\bdpm\raw")
CIS_CIP_FILE = BDPM_DIR / "CIS_CIP_bdpm.txt"


def parse_pfht_from_bdpm(filepath: Path) -> dict:
    """
    Parse CIS_CIP_bdpm.txt pour extraire CIP13 -> PFHT.

    Format: CIS | code | libelle | statut | type | date | CIP13 | agrement | taux | PFHT | ...
    """
    cip_to_pfht = {}

    with open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 10:
                cip13 = parts[6].strip()
                pfht_str = parts[9].strip().replace(',', '.')

                # Valider CIP13 et PFHT
                if cip13 and len(cip13) == 13 and cip13.isdigit() and pfht_str:
                    try:
                        pfht = Decimal(pfht_str)
                        cip_to_pfht[cip13] = pfht
                    except:
                        pass

    return cip_to_pfht


def update_catalogues_pfht():
    """Met a jour prix_fabricant dans catalogue_produits."""

    print(f"Lecture des PFHT depuis {CIS_CIP_FILE}...")
    cip_to_pfht = parse_pfht_from_bdpm(CIS_CIP_FILE)
    print(f"  -> {len(cip_to_pfht)} CIP avec PFHT dans BDPM")

    db = SessionLocal()
    try:
        # Recuperer les CIP existants dans les catalogues
        result = db.execute(text("""
            SELECT DISTINCT code_cip FROM catalogue_produits
            WHERE code_cip IS NOT NULL
        """))
        catalogue_cips = {row[0] for row in result}
        print(f"  -> {len(catalogue_cips)} CIP dans tes catalogues")

        # Trouver les CIP communs
        cips_to_update = catalogue_cips & set(cip_to_pfht.keys())
        print(f"  -> {len(cips_to_update)} CIP a mettre a jour")

        if not cips_to_update:
            print("Aucun CIP a mettre a jour.")
            return

        # Mettre a jour par batch
        updated = 0
        for cip in cips_to_update:
            pfht = cip_to_pfht[cip]
            db.execute(
                text("UPDATE catalogue_produits SET prix_fabricant = :pfht WHERE code_cip = :cip"),
                {"pfht": pfht, "cip": cip}
            )
            updated += 1

            if updated % 500 == 0:
                print(f"  {updated} / {len(cips_to_update)} mis a jour...")

        db.commit()
        print(f"\nTermine: {updated} produits mis a jour avec leur PFHT")

        # Stats
        result = db.execute(text("""
            SELECT COUNT(*) FROM catalogue_produits WHERE prix_fabricant IS NOT NULL
        """))
        total_with_pfht = result.scalar()
        result = db.execute(text("SELECT COUNT(*) FROM catalogue_produits"))
        total = result.scalar()
        print(f"  -> {total_with_pfht}/{total} produits ont maintenant un PFHT ({100*total_with_pfht/total:.1f}%)")

    except Exception as e:
        db.rollback()
        print(f"Erreur: {e}")
        raise
    finally:
        db.close()


def main():
    print("=" * 60)
    print("MISE A JOUR PFHT - Catalogues labos uniquement")
    print("=" * 60)

    if not CIS_CIP_FILE.exists():
        print(f"ERREUR: Fichier non trouve: {CIS_CIP_FILE}")
        sys.exit(1)

    update_catalogues_pfht()

    print("=" * 60)
    print("TERMINE")
    print("=" * 60)


if __name__ == "__main__":
    main()
