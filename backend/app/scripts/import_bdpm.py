"""
Script d'import des donnees BDPM pour le matching par groupe generique.

Parse les fichiers CIS_CIP_bdpm.txt et CIS_GENER_bdpm.txt pour creer
une table de lookup CIP13 -> groupe_generique_id.

Usage:
    cd C:\pharma-remises\backend
    python -m app.scripts.import_bdpm
"""
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.db.database import engine, SessionLocal
from app.models import BdpmEquivalence


# Chemins des fichiers BDPM
BDPM_DIR = Path(r"C:\pdf-extractor\data\bdpm\raw")
CIS_CIP_FILE = BDPM_DIR / "CIS_CIP_bdpm.txt"
CIS_GENER_FILE = BDPM_DIR / "CIS_GENER_bdpm.txt"


def parse_cis_cip(filepath: Path) -> dict:
    """
    Parse CIS_CIP_bdpm.txt pour extraire CIP13 -> (CIS, PFHT).

    Format: CIS | code_presentation | libelle | statut | type | date | CIP13 | agrement | taux_remb | PFHT | ...
    """
    cip_to_info = {}

    with open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                cis = parts[0].strip()
                cip13 = parts[6].strip()

                # Extraire PFHT (colonne 9) si disponible
                pfht = None
                if len(parts) >= 10:
                    pfht_str = parts[9].strip().replace(',', '.')
                    try:
                        pfht = float(pfht_str) if pfht_str else None
                    except ValueError:
                        pfht = None

                # Valider CIP13 (13 chiffres)
                if cip13 and len(cip13) == 13 and cip13.isdigit():
                    cip_to_info[cip13] = {'cis': cis, 'pfht': pfht}

    return cip_to_info


def parse_cis_gener(filepath: Path) -> dict:
    """
    Parse CIS_GENER_bdpm.txt pour extraire CIS -> (groupe_generique_id, libelle, type).

    Format: groupe_generique_id | libelle_groupe | CIS | type (0=princeps, 1=gen) | tri
    """
    cis_to_groupe = {}

    with open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                groupe_id = parts[0].strip()
                libelle = parts[1].strip()
                cis = parts[2].strip()
                type_gen = parts[3].strip()

                try:
                    groupe_id_int = int(groupe_id)
                    type_gen_int = int(type_gen) if type_gen.isdigit() else None

                    cis_to_groupe[cis] = {
                        'groupe_generique_id': groupe_id_int,
                        'libelle_groupe': libelle,
                        'type_generique': type_gen_int
                    }
                except ValueError:
                    continue

    return cis_to_groupe


def create_table_if_not_exists():
    """Cree la table bdpm_equivalences si elle n'existe pas."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bdpm_equivalences (
                cip13 VARCHAR(13) PRIMARY KEY,
                cis VARCHAR(20),
                groupe_generique_id INTEGER,
                libelle_groupe VARCHAR(500),
                type_generique INTEGER,
                pfht NUMERIC(10, 2),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bdpm_cis ON bdpm_equivalences(cis)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bdpm_groupe ON bdpm_equivalences(groupe_generique_id)"))
        # Ajouter colonne pfht si elle n'existe pas (pour migration)
        conn.execute(text("""
            DO $$
            BEGIN
                ALTER TABLE bdpm_equivalences ADD COLUMN IF NOT EXISTS pfht NUMERIC(10, 2);
            EXCEPTION WHEN duplicate_column THEN
                NULL;
            END $$;
        """))
        conn.commit()
    print("Table bdpm_equivalences creee/verifiee (avec PFHT)")


def import_bdpm_data():
    """Import les donnees BDPM dans la table bdpm_equivalences."""

    print(f"Lecture de {CIS_CIP_FILE}...")
    cip_to_info = parse_cis_cip(CIS_CIP_FILE)
    print(f"  -> {len(cip_to_info)} CIP13 trouves")

    print(f"Lecture de {CIS_GENER_FILE}...")
    cis_to_groupe = parse_cis_gener(CIS_GENER_FILE)
    print(f"  -> {len(cis_to_groupe)} CIS avec groupe generique")

    # Joindre les deux pour avoir CIP13 -> groupe_generique + pfht
    records = []
    matched = 0
    with_pfht = 0

    for cip13, info in cip_to_info.items():
        cis = info['cis']
        pfht = info['pfht']

        record = {
            'cip13': cip13,
            'cis': cis,
            'groupe_generique_id': None,
            'libelle_groupe': None,
            'type_generique': None,
            'pfht': pfht
        }

        if pfht is not None:
            with_pfht += 1

        if cis in cis_to_groupe:
            groupe_info = cis_to_groupe[cis]
            record['groupe_generique_id'] = groupe_info['groupe_generique_id']
            record['libelle_groupe'] = groupe_info['libelle_groupe'][:500] if groupe_info['libelle_groupe'] else None
            record['type_generique'] = groupe_info['type_generique']
            matched += 1

        records.append(record)

    print(f"  -> {matched} CIP13 avec groupe generique ({100*matched/len(records):.1f}%)")
    print(f"  -> {with_pfht} CIP13 avec PFHT ({100*with_pfht/len(records):.1f}%)")

    # Inserer en batch
    print("Insertion dans la base...")
    db = SessionLocal()
    try:
        # Vider la table existante
        db.execute(text("TRUNCATE TABLE bdpm_equivalences"))

        # Inserer par batch de 1000
        batch_size = 1000
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            db.bulk_insert_mappings(BdpmEquivalence, batch)
            if (i + batch_size) % 5000 == 0:
                print(f"  {i + batch_size} / {len(records)} inseres...")

        db.commit()
        print(f"Import termine: {len(records)} enregistrements")

    except Exception as e:
        db.rollback()
        print(f"Erreur: {e}")
        raise
    finally:
        db.close()


def main():
    """Point d'entree principal."""
    print("=" * 60)
    print("IMPORT BDPM - Referentiel groupe generique")
    print("=" * 60)

    # Verifier que les fichiers existent
    if not CIS_CIP_FILE.exists():
        print(f"ERREUR: Fichier non trouve: {CIS_CIP_FILE}")
        sys.exit(1)
    if not CIS_GENER_FILE.exists():
        print(f"ERREUR: Fichier non trouve: {CIS_GENER_FILE}")
        sys.exit(1)

    # Creer la table
    create_table_if_not_exists()

    # Importer les donnees
    import_bdpm_data()

    print("=" * 60)
    print("TERMINE")
    print("=" * 60)


if __name__ == "__main__":
    main()
