"""
Service de matching intelligent pour produits pharmaceutiques.

Utilise RapidFuzz pour le fuzzy matching et groupe_generique_id BDPM comme signal principal.
Inspire de l'algorithme PMC3243188 (Clinical Drug Name Matching).
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal

from rapidfuzz import fuzz, process, utils
from cachetools import TTLCache
from sqlalchemy.orm import Session

from app.models import CatalogueProduit, Laboratoire, MesVentes, BdpmEquivalence

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MoleculeComponents:
    """Composants extraits d'une designation de medicament."""
    molecule: str = ""
    dosage: Optional[str] = None
    forme: Optional[str] = None
    conditionnement: Optional[int] = None
    princeps: Optional[str] = None
    raw_text: str = ""


@dataclass
class MatchResult:
    """Resultat d'un matching produit."""
    produit_id: int
    laboratoire_id: int
    laboratoire_nom: str
    code_cip: str
    nom_commercial: str
    groupe_generique_id: Optional[int]
    score: float
    match_type: str  # 'exact_cip', 'groupe_generique', 'fuzzy_molecule', 'fuzzy_commercial'
    prix_fabricant: Optional[Decimal] = None
    remise_pct: Optional[Decimal] = None
    matched_on: Optional[str] = None  # Valeur qui a permis le match


@dataclass
class VenteMatchingResult:
    """Resultat du matching pour une vente."""
    vente_id: int
    designation: str
    code_cip_achete: Optional[str]
    montant_annuel: Decimal
    quantite_annuelle: int
    matches: List[MatchResult] = field(default_factory=list)
    best_match_by_lab: Dict[int, MatchResult] = field(default_factory=dict)
    unmatched: bool = False


# =============================================================================
# MOLECULE EXTRACTOR
# =============================================================================

class MoleculeExtractor:
    """
    Extracteur de composants (molecule, dosage, forme) depuis les noms de medicaments.

    Supporte deux formats:
    - libelle_groupe BDPM: "MOLECULE DOSAGE - PRINCEPS DOSAGE, forme"
    - nom_commercial: "MOLECULE LABO DOSAGEmg Forme B/QTE"
    """

    # Formes pharmaceutiques connues et leur normalisation
    FORMES_MAPPING = {
        'cpr': 'comprime',
        'cp': 'comprime',
        'comp': 'comprime',
        'comprime': 'comprime',
        'gel': 'gelule',
        'gelule': 'gelule',
        'caps': 'capsule',
        'capsule': 'capsule',
        'sol': 'solution',
        'solution': 'solution',
        'susp': 'suspension',
        'suspension': 'suspension',
        'inj': 'injectable',
        'injectable': 'injectable',
        'sirop': 'sirop',
        'cr': 'creme',
        'creme': 'creme',
        'pom': 'pommade',
        'pommade': 'pommade',
        'sachet': 'sachet',
        'patch': 'patch',
        'collyre': 'collyre',
        'spray': 'spray',
        'aerosol': 'aerosol',
        'suppo': 'suppositoire',
        'suppositoire': 'suppositoire',
        'ovule': 'ovule',
        'granule': 'granule',
        'pdre': 'poudre',
        'poudre': 'poudre',
        'fl': 'flacon',
        'flacon': 'flacon',
        'amp': 'ampoule',
        'ampoule': 'ampoule',
    }

    # Noms de laboratoires a filtrer
    LABOS_CONNUS = {
        'viatris', 'zentiva', 'biogaran', 'sandoz', 'teva', 'mylan', 'arrow',
        'eg', 'cristers', 'accord', 'ranbaxy', 'zydus', 'sun', 'almus', 'bgr',
        'ratiopharm', 'actavis', 'winthrop', 'pfizer', 'sanofi', 'bayer',
        'novartis', 'roche', 'merck', 'gsk', 'astrazeneca', 'lilly', 'abbott',
        'lab', 'labo', 'laboratoire', 'generique', 'generic', 'gen'
    }

    # Pattern pour dosage
    DOSAGE_PATTERN = re.compile(
        r'(\d+[\d,\.]*\s*(?:mg|g|ml|%|microgrammes?|mcg|ui|mmol|µg)(?:/\s*\d+\s*(?:ml|g|dose))?)',
        re.IGNORECASE
    )

    # Pattern pour conditionnement
    CONDITIONNEMENT_PATTERN = re.compile(
        r'[Bb]/?\s*(\d+)|(?:bt|bte|boite|plq)?\s*(?:de\s+)?(\d+)\s*(?:cpr|cp|gel|caps|comp)',
        re.IGNORECASE
    )

    def extract_from_libelle_groupe(self, libelle: str) -> MoleculeComponents:
        """
        Extrait les composants depuis un libelle_groupe BDPM.

        Format: "MOLECULE DOSAGE - PRINCEPS DOSAGE, forme"
        Exemple: "RAMIPRIL 10 mg - TRIATEC 10 mg, comprime"
        """
        if not libelle:
            return MoleculeComponents(raw_text=libelle or "")

        result = MoleculeComponents(raw_text=libelle)

        # Split sur " - " pour separer generique/princeps
        parts = libelle.split(' - ')
        generic_part = parts[0].strip()
        princeps_part = parts[1].strip() if len(parts) > 1 else None

        # Extraire la forme (apres la derniere virgule)
        if ',' in libelle:
            forme_text = libelle.rsplit(',', 1)[1].strip().lower()
            # Chercher une forme connue
            for abbr, full in self.FORMES_MAPPING.items():
                if abbr in forme_text or full in forme_text:
                    result.forme = full
                    break
            if not result.forme:
                result.forme = forme_text

        # Extraire le dosage du generic_part
        dosage_match = self.DOSAGE_PATTERN.search(generic_part)
        if dosage_match:
            result.dosage = self._normalize_dosage(dosage_match.group(1))

        # Molecule = ce qui reste apres avoir enleve le dosage
        molecule_text = self.DOSAGE_PATTERN.sub('', generic_part).strip()
        molecule_text = re.sub(r'\s+', ' ', molecule_text)
        result.molecule = molecule_text.upper()

        # Extraire le princeps
        if princeps_part:
            princeps_clean = princeps_part.split(',')[0]
            princeps_clean = self.DOSAGE_PATTERN.sub('', princeps_clean).strip()
            result.princeps = princeps_clean

        return result

    def extract_from_commercial_name(self, name: str) -> MoleculeComponents:
        """
        Extrait les composants depuis un nom commercial.

        Format: "MOLECULE LABO DOSAGEmg Forme B/QTE"
        Exemple: "FUROSEMIDE VIATRIS 40mg Cpr B/30"
        """
        if not name:
            return MoleculeComponents(raw_text=name or "")

        result = MoleculeComponents(raw_text=name)
        text = name.strip()

        # Extraire le dosage
        dosage_match = self.DOSAGE_PATTERN.search(text)
        if dosage_match:
            result.dosage = self._normalize_dosage(dosage_match.group(1))

        # Extraire le conditionnement
        cond_match = self.CONDITIONNEMENT_PATTERN.search(text)
        if cond_match:
            cond_str = cond_match.group(1) or cond_match.group(2)
            if cond_str:
                try:
                    result.conditionnement = int(cond_str)
                except ValueError:
                    pass

        # Extraire la forme
        text_lower = text.lower()
        for abbr, full in self.FORMES_MAPPING.items():
            if re.search(rf'\b{re.escape(abbr)}\b', text_lower):
                result.forme = full
                break

        # Extraire la molecule (mots significatifs avant le dosage)
        words = text.split()
        molecule_parts = []

        for word in words:
            word_clean = re.sub(r'[^\w]', '', word).lower()

            # Arreter si on atteint un chiffre (debut du dosage)
            if re.match(r'^\d', word_clean):
                break

            # Ignorer les labos et mots courts
            if word_clean in self.LABOS_CONNUS:
                continue
            if len(word_clean) <= 2:
                continue

            # Ignorer les formes
            if word_clean in self.FORMES_MAPPING:
                continue

            molecule_parts.append(word_clean.upper())

            # Generalement 1-2 mots pour la molecule
            if len(molecule_parts) >= 2:
                break

        result.molecule = ' '.join(molecule_parts)

        return result

    def _normalize_dosage(self, dosage: str) -> str:
        """Normalise un dosage (enleve espaces, standardise)."""
        if not dosage:
            return ""
        # Enlever espaces internes
        normalized = re.sub(r'\s+', '', dosage.lower())
        # Remplacer virgule par point
        normalized = normalized.replace(',', '.')
        return normalized

    def extract(self, text: str) -> MoleculeComponents:
        """
        Methode principale d'extraction - detecte automatiquement le format.

        Si le texte contient " - " c'est probablement un libelle_groupe BDPM,
        sinon c'est un nom commercial.

        Args:
            text: Texte a analyser (designation vente ou libelle BDPM)

        Returns:
            MoleculeComponents avec molecule, dosage, forme extraits
        """
        if not text:
            return MoleculeComponents(raw_text="")

        # Detection du format
        if ' - ' in text and ('mg' in text.lower() or 'ml' in text.lower()):
            # Format BDPM: "MOLECULE DOSAGE - PRINCEPS DOSAGE, forme"
            return self.extract_from_libelle_groupe(text)
        else:
            # Format commercial: "MOLECULE LABO DOSAGEmg Forme B/QTE"
            return self.extract_from_commercial_name(text)


# =============================================================================
# FUZZY MATCHER
# =============================================================================

class FuzzyMatcher:
    """
    Wrapper RapidFuzz pour le matching de noms pharmaceutiques.
    """

    def __init__(self, score_cutoff: float = 60.0):
        self.score_cutoff = score_cutoff

    def match_molecule(
        self,
        query: str,
        choices: List[str],
        limit: int = 5
    ) -> List[Tuple[str, float, int]]:
        """
        Trouve les meilleures correspondances de molecule.
        Utilise WRatio avec preprocessing pour ignorer la casse.
        """
        if not query or not choices:
            return []

        return process.extract(
            query,
            choices,
            scorer=fuzz.WRatio,
            processor=utils.default_process,
            limit=limit,
            score_cutoff=self.score_cutoff
        )

    def match_commercial_name(
        self,
        query: str,
        choices: List[str],
        limit: int = 5
    ) -> List[Tuple[str, float, int]]:
        """
        Trouve les meilleures correspondances de nom commercial.
        Utilise partial_ratio pour les sous-chaines.
        """
        if not query or not choices:
            return []

        return process.extract(
            query,
            choices,
            scorer=fuzz.partial_ratio,
            processor=utils.default_process,
            limit=limit,
            score_cutoff=self.score_cutoff
        )

    def calculate_component_score(
        self,
        query_comp: MoleculeComponents,
        target_comp: MoleculeComponents
    ) -> float:
        """
        Calcule un score pondere base sur les composants.

        Poids:
        - Molecule: 50%
        - Dosage: 30%
        - Forme: 20%
        """
        scores = []
        weights = []

        # Score molecule (50%)
        if query_comp.molecule and target_comp.molecule:
            mol_score = fuzz.WRatio(
                query_comp.molecule,
                target_comp.molecule,
                processor=utils.default_process
            )
            scores.append(mol_score)
            weights.append(0.50)

        # Score dosage (30%)
        if query_comp.dosage and target_comp.dosage:
            q_dos = query_comp.dosage.lower().replace(' ', '')
            t_dos = target_comp.dosage.lower().replace(' ', '')
            dos_score = 100.0 if q_dos == t_dos else fuzz.ratio(q_dos, t_dos)
            scores.append(dos_score)
            weights.append(0.30)

        # Score forme (20%)
        if query_comp.forme and target_comp.forme:
            form_score = fuzz.partial_ratio(
                query_comp.forme,
                target_comp.forme,
                processor=utils.default_process
            )
            scores.append(form_score)
            weights.append(0.20)

        if not scores:
            return 0.0

        # Normaliser les poids si tous les composants ne sont pas presents
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        return sum(s * w for s, w in zip(scores, normalized_weights))


# =============================================================================
# INTELLIGENT MATCHER
# =============================================================================

class IntelligentMatcher:
    """
    Orchestrateur de matching multi-signal pour produits pharmaceutiques.

    Priorite des signaux:
    1. Code CIP exact (100%)
    2. groupe_generique_id BDPM (100% si match)
    3. Fuzzy molecule + dosage + forme (max 85%)
    4. Fuzzy nom commercial (max 70%)
    """

    def __init__(self, db: Session):
        self.db = db
        self.extractor = MoleculeExtractor()
        self.fuzzy = FuzzyMatcher(score_cutoff=60.0)
        self._cache = TTLCache(maxsize=1000, ttl=300)  # Cache 5 min

    def _get_all_products_by_lab(self) -> Dict[int, List[CatalogueProduit]]:
        """Recupere tous les produits groupes par labo (cache)."""
        cache_key = "all_products_by_lab"
        if cache_key in self._cache:
            return self._cache[cache_key]

        products = self.db.query(CatalogueProduit).filter(
            CatalogueProduit.actif == True
        ).all()

        result = {}
        for p in products:
            if p.laboratoire_id not in result:
                result[p.laboratoire_id] = []
            result[p.laboratoire_id].append(p)

        self._cache[cache_key] = result
        return result

    def _get_labs_map(self) -> Dict[int, str]:
        """Recupere le mapping id -> nom des labos."""
        cache_key = "labs_map"
        if cache_key in self._cache:
            return self._cache[cache_key]

        labs = self.db.query(Laboratoire).filter(Laboratoire.actif == True).all()
        result = {l.id: l.nom for l in labs}
        self._cache[cache_key] = result
        return result

    def _get_products_by_cip(self) -> Dict[str, List[CatalogueProduit]]:
        """Index des produits par code CIP."""
        cache_key = "products_by_cip"
        if cache_key in self._cache:
            return self._cache[cache_key]

        products = self.db.query(CatalogueProduit).filter(
            CatalogueProduit.actif == True,
            CatalogueProduit.code_cip.isnot(None)
        ).all()

        result = {}
        for p in products:
            if p.code_cip:
                cip = p.code_cip.strip()
                if cip not in result:
                    result[cip] = []
                result[cip].append(p)

        self._cache[cache_key] = result
        return result

    def _get_products_by_groupe(self) -> Dict[int, List[CatalogueProduit]]:
        """Index des produits par groupe_generique_id."""
        cache_key = "products_by_groupe"
        if cache_key in self._cache:
            return self._cache[cache_key]

        products = self.db.query(CatalogueProduit).filter(
            CatalogueProduit.actif == True,
            CatalogueProduit.groupe_generique_id.isnot(None)
        ).all()

        result = {}
        for p in products:
            gid = p.groupe_generique_id
            if gid not in result:
                result[gid] = []
            result[gid].append(p)

        self._cache[cache_key] = result
        return result

    def _lookup_groupe_from_bdpm(self, cip: str) -> Optional[Tuple[int, str]]:
        """
        Lookup groupe_generique_id depuis la table BDPM.

        Permet de trouver le groupe meme si le produit vient d'un labo
        non importe dans le systeme (BIOGARAN, TEVA, EG, etc.)

        Returns:
            Tuple (groupe_generique_id, libelle_groupe) ou None
        """
        if not cip:
            return None

        cache_key = f"bdpm_lookup_{cip}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Nettoyer le CIP (garder les 13 derniers chiffres)
        cip_clean = ''.join(c for c in cip if c.isdigit())
        if len(cip_clean) > 13:
            cip_clean = cip_clean[-13:]

        bdpm = self.db.query(BdpmEquivalence).filter(
            BdpmEquivalence.cip13 == cip_clean
        ).first()

        if bdpm and bdpm.groupe_generique_id:
            result = (bdpm.groupe_generique_id, bdpm.libelle_groupe)
        else:
            result = None

        self._cache[cache_key] = result
        return result

    def find_matches_for_product(
        self,
        designation: str,
        code_cip: Optional[str] = None,
        target_lab_id: Optional[int] = None
    ) -> List[MatchResult]:
        """
        Trouve les correspondances pour un produit donne.

        Priorite des signaux:
        1. Code CIP exact dans catalogue (100%)
        2. groupe_generique_id via BDPM lookup (95%)
        3. Fuzzy molecule + dosage + forme (max 85%)
        4. Fuzzy nom commercial (max 70%)

        Args:
            designation: Nom commercial du produit
            code_cip: Code CIP optionnel
            target_lab_id: Si specifie, cherche uniquement dans ce labo

        Returns:
            Liste de MatchResult tries par score decroissant
        """
        results = []
        labs_map = self._get_labs_map()

        # 1. Match par CIP exact dans le catalogue (priorite max)
        if code_cip:
            cip_products = self._get_products_by_cip()
            cip_clean = code_cip.strip()
            if cip_clean in cip_products:
                for p in cip_products[cip_clean]:
                    if target_lab_id and p.laboratoire_id != target_lab_id:
                        continue
                    results.append(MatchResult(
                        produit_id=p.id,
                        laboratoire_id=p.laboratoire_id,
                        laboratoire_nom=labs_map.get(p.laboratoire_id, "?"),
                        code_cip=p.code_cip,
                        nom_commercial=p.nom_commercial or "",
                        groupe_generique_id=p.groupe_generique_id,
                        score=100.0,
                        match_type='exact_cip',
                        prix_fabricant=p.prix_fabricant,
                        remise_pct=p.remise_pct
                    ))

        # Si on a des matchs CIP exacts, les retourner directement
        if results:
            return sorted(results, key=lambda x: (-x.score, x.laboratoire_nom))

        # 2. Match par groupe_generique_id via BDPM lookup
        # Cela permet de trouver des equivalents meme si le labo d'origine
        # (BIOGARAN, TEVA, EG...) n'est pas importe dans le systeme
        if code_cip:
            bdpm_result = self._lookup_groupe_from_bdpm(code_cip)
            if bdpm_result:
                groupe_id, libelle_groupe = bdpm_result
                products_by_groupe = self._get_products_by_groupe()

                if groupe_id in products_by_groupe:
                    for p in products_by_groupe[groupe_id]:
                        if target_lab_id and p.laboratoire_id != target_lab_id:
                            continue
                        results.append(MatchResult(
                            produit_id=p.id,
                            laboratoire_id=p.laboratoire_id,
                            laboratoire_nom=labs_map.get(p.laboratoire_id, "?"),
                            code_cip=p.code_cip or "",
                            nom_commercial=p.nom_commercial or "",
                            groupe_generique_id=p.groupe_generique_id,
                            score=95.0,  # Tres bon score car meme groupe generique
                            match_type='groupe_generique_bdpm',
                            prix_fabricant=p.prix_fabricant,
                            remise_pct=p.remise_pct,
                            matched_on=f"Groupe {groupe_id}"
                        ))

        # Si on a des matchs par groupe BDPM, les retourner
        if results:
            return sorted(results, key=lambda x: (-x.score, x.laboratoire_nom))

        # 3. Extraire les composants de la designation pour fuzzy matching
        query_components = self.extractor.extract_from_commercial_name(designation)

        # 4. Chercher par fuzzy matching sur molecule
        products_by_groupe = self._get_products_by_groupe()
        all_products = self.db.query(CatalogueProduit).filter(
            CatalogueProduit.actif == True
        ).all()

        # Construire un index molecule -> produits pour le fuzzy matching
        molecule_to_products = {}
        for p in all_products:
            if target_lab_id and p.laboratoire_id != target_lab_id:
                continue

            if p.libelle_groupe:
                target_comp = self.extractor.extract_from_libelle_groupe(p.libelle_groupe)
            else:
                target_comp = self.extractor.extract_from_commercial_name(p.nom_commercial or "")

            if target_comp.molecule:
                mol_key = target_comp.molecule.upper()
                if mol_key not in molecule_to_products:
                    molecule_to_products[mol_key] = []
                molecule_to_products[mol_key].append((p, target_comp))

        # Fuzzy match sur les molecules
        if query_components.molecule and molecule_to_products:
            molecule_choices = list(molecule_to_products.keys())
            fuzzy_matches = self.fuzzy.match_molecule(
                query_components.molecule,
                molecule_choices,
                limit=10
            )

            seen_products = set()  # Eviter les doublons

            for matched_mol, mol_score, _ in fuzzy_matches:
                for p, target_comp in molecule_to_products.get(matched_mol, []):
                    if p.id in seen_products:
                        continue
                    seen_products.add(p.id)

                    # Calculer score composite
                    component_score = self.fuzzy.calculate_component_score(
                        query_components, target_comp
                    )

                    # Determiner le type de match et ajuster le score
                    if p.groupe_generique_id and mol_score >= 95:
                        match_type = 'groupe_generique'
                        final_score = min(100.0, component_score * 1.05)  # Bonus groupe
                    else:
                        match_type = 'fuzzy_molecule'
                        final_score = component_score * 0.85  # Cap a 85%

                    if final_score >= 60:  # Seuil minimum
                        results.append(MatchResult(
                            produit_id=p.id,
                            laboratoire_id=p.laboratoire_id,
                            laboratoire_nom=labs_map.get(p.laboratoire_id, "?"),
                            code_cip=p.code_cip or "",
                            nom_commercial=p.nom_commercial or "",
                            groupe_generique_id=p.groupe_generique_id,
                            score=round(final_score, 2),
                            match_type=match_type,
                            prix_fabricant=p.prix_fabricant,
                            remise_pct=p.remise_pct
                        ))

        # 4. Fallback: fuzzy sur nom commercial complet
        if not results:
            all_products_filtered = [
                p for p in all_products
                if (not target_lab_id or p.laboratoire_id == target_lab_id)
                and p.nom_commercial
            ]

            if all_products_filtered:
                product_names = [p.nom_commercial for p in all_products_filtered]
                fuzzy_matches = self.fuzzy.match_commercial_name(
                    designation,
                    product_names,
                    limit=5
                )

                for matched_name, name_score, idx in fuzzy_matches:
                    p = all_products_filtered[idx]
                    final_score = name_score * 0.70  # Cap a 70%

                    if final_score >= 50:  # Seuil plus bas pour fallback
                        results.append(MatchResult(
                            produit_id=p.id,
                            laboratoire_id=p.laboratoire_id,
                            laboratoire_nom=labs_map.get(p.laboratoire_id, "?"),
                            code_cip=p.code_cip or "",
                            nom_commercial=p.nom_commercial or "",
                            groupe_generique_id=p.groupe_generique_id,
                            score=round(final_score, 2),
                            match_type='fuzzy_commercial',
                            prix_fabricant=p.prix_fabricant,
                            remise_pct=p.remise_pct
                        ))

        # Trier par score decroissant, puis par nom de labo
        return sorted(results, key=lambda x: (-x.score, x.laboratoire_nom))

    def match_ventes_to_catalogues(
        self,
        ventes: List[MesVentes],
        min_score: float = 60.0
    ) -> List[VenteMatchingResult]:
        """
        Matche une liste de ventes avec les catalogues de tous les labos.

        Args:
            ventes: Liste des ventes a matcher
            min_score: Score minimum pour considerer un match valide

        Returns:
            Liste de VenteMatchingResult avec les meilleurs matchs par labo
        """
        results = []
        labs_map = self._get_labs_map()

        logger.info(f"Matching {len(ventes)} ventes avec {len(labs_map)} labos...")

        for vente in ventes:
            vente_result = VenteMatchingResult(
                vente_id=vente.id,
                designation=vente.designation or "",
                code_cip_achete=vente.code_cip_achete,
                montant_annuel=vente.montant_annuel or Decimal('0'),
                quantite_annuelle=vente.quantite_annuelle or 0
            )

            # Chercher les matchs pour cette vente
            matches = self.find_matches_for_product(
                designation=vente.designation or "",
                code_cip=vente.code_cip_achete
            )

            # Filtrer par score minimum et grouper par labo
            valid_matches = [m for m in matches if m.score >= min_score]

            if valid_matches:
                vente_result.matches = valid_matches

                # Garder le meilleur match par labo
                for match in valid_matches:
                    lab_id = match.laboratoire_id
                    if lab_id not in vente_result.best_match_by_lab:
                        vente_result.best_match_by_lab[lab_id] = match
                    elif match.score > vente_result.best_match_by_lab[lab_id].score:
                        vente_result.best_match_by_lab[lab_id] = match
            else:
                vente_result.unmatched = True

            results.append(vente_result)

        # Stats
        matched = sum(1 for r in results if not r.unmatched)
        unmatched = sum(1 for r in results if r.unmatched)
        logger.info(f"Matching termine: {matched} matches, {unmatched} non-matches")

        return results

    def clear_cache(self):
        """Vide le cache (utile apres import de nouveaux produits)."""
        self._cache.clear()
        logger.info("Cache IntelligentMatcher vide")
