"""Service d'optimisation de combinaison de labos.

Trouve la meilleure combinaison de labos pour maximiser:
1. La couverture (produits disponibles)
2. Le montant total de remises (pas juste le pourcentage)

Algorithme:
1. Calculer la couverture du labo principal
2. Pour le chiffre "perdu", evaluer chaque labo complementaire
3. Trier par MONTANT de remise total (pas %)
4. Suggerer les meilleures combos

Reference: Inspire de l'algorithme Set Cover (NP-hard) mais avec heuristique greedy
car on optimise pour le montant de remise, pas juste la couverture.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict, Set, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import (
    MesVentes, VenteMatching, Laboratoire, CatalogueProduit
)


@dataclass
class LaboCoverage:
    """Couverture d'un labo sur les ventes."""
    labo_id: int
    labo_nom: str
    remise_negociee: Decimal
    ventes_couvertes: Set[int]  # IDs des ventes matchees
    montant_couvert: Decimal
    nb_produits: int


@dataclass
class ComboResult:
    """Resultat d'une combinaison de labos."""
    labos: List[LaboCoverage]
    couverture_totale_pct: float
    chiffre_total_realise: Decimal
    montant_remise_total: Decimal
    ventes_non_couvertes: Set[int]


class ComboOptimizer:
    """Optimiseur de combinaison de labos."""

    def __init__(self, db: Session):
        self.db = db

    def calculate_lab_coverage(
        self,
        labo_id: int,
        vente_ids: List[int],
        ventes_map: Dict[int, MesVentes]
    ) -> LaboCoverage:
        """Calcule la couverture d'un labo sur un ensemble de ventes."""
        labo = self.db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
        if not labo:
            return LaboCoverage(
                labo_id=labo_id,
                labo_nom="?",
                remise_negociee=Decimal("0"),
                ventes_couvertes=set(),
                montant_couvert=Decimal("0"),
                nb_produits=0
            )

        # Recuperer les matchings pour ce labo
        matchings = self.db.query(VenteMatching).filter(
            VenteMatching.vente_id.in_(vente_ids),
            VenteMatching.labo_id == labo_id,
            VenteMatching.produit_id.isnot(None)  # Match valide
        ).all()

        ventes_couvertes = set()
        montant_couvert = Decimal("0")

        for m in matchings:
            ventes_couvertes.add(m.vente_id)
            vente = ventes_map.get(m.vente_id)
            if vente:
                montant_couvert += vente.montant_annuel or Decimal("0")

        return LaboCoverage(
            labo_id=labo_id,
            labo_nom=labo.nom,
            remise_negociee=labo.remise_negociee or Decimal("0"),
            ventes_couvertes=ventes_couvertes,
            montant_couvert=montant_couvert,
            nb_produits=len(ventes_couvertes)
        )

    def estimate_remise(
        self,
        labo_coverage: LaboCoverage,
        include_remise_ligne: bool = True
    ) -> Decimal:
        """
        Estime le montant total de remise pour un labo.

        Pour simplifier, on utilise remise_negociee * montant_couvert.
        En realite, il faudrait calculer remise_ligne + remontee pour chaque produit.
        """
        if labo_coverage.montant_couvert <= 0:
            return Decimal("0")

        # Estimation simplifiee: montant * remise_negociee
        return labo_coverage.montant_couvert * labo_coverage.remise_negociee / 100

    def find_best_combo_greedy(
        self,
        import_id: int,
        labo_principal_id: int,
        max_labos_combo: int = 3
    ) -> ComboResult:
        """
        Trouve la meilleure combinaison de labos avec algorithme greedy.

        Algorithme:
        1. Commencer avec le labo principal
        2. Pour les ventes non couvertes, evaluer chaque labo complementaire
        3. Ajouter celui qui apporte le plus de MONTANT de remise
        4. Repeter jusqu'a max_labos_combo ou couverture 100%

        Args:
            import_id: ID de l'import ventes
            labo_principal_id: ID du labo principal
            max_labos_combo: Nombre max de labos dans la combo

        Returns:
            ComboResult avec les labos optimaux
        """
        # Recuperer toutes les ventes
        ventes = self.db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
        if not ventes:
            return ComboResult(
                labos=[],
                couverture_totale_pct=0,
                chiffre_total_realise=Decimal("0"),
                montant_remise_total=Decimal("0"),
                ventes_non_couvertes=set()
            )

        vente_ids = [v.id for v in ventes]
        ventes_map = {v.id: v for v in ventes}
        chiffre_total = sum(v.montant_annuel or Decimal("0") for v in ventes)

        # Couverture du labo principal
        coverage_principal = self.calculate_lab_coverage(labo_principal_id, vente_ids, ventes_map)

        selected_labos = [coverage_principal]
        ventes_couvertes = coverage_principal.ventes_couvertes.copy()
        montant_remise_total = self.estimate_remise(coverage_principal)

        # Recuperer tous les autres labos actifs
        other_labos = self.db.query(Laboratoire).filter(
            Laboratoire.id != labo_principal_id,
            Laboratoire.actif == True
        ).all()

        # Greedy: ajouter les labos complementaires
        for _ in range(max_labos_combo - 1):
            ventes_restantes = set(vente_ids) - ventes_couvertes
            if not ventes_restantes:
                break  # Couverture 100%

            # Evaluer chaque labo sur les ventes restantes
            best_labo = None
            best_remise_add = Decimal("0")

            for labo in other_labos:
                if any(l.labo_id == labo.id for l in selected_labos):
                    continue  # Deja dans la combo

                # Calculer couverture sur les ventes RESTANTES
                coverage = self.calculate_lab_coverage(
                    labo.id,
                    list(ventes_restantes),
                    ventes_map
                )

                if not coverage.ventes_couvertes:
                    continue

                remise_add = self.estimate_remise(coverage)

                if remise_add > best_remise_add:
                    best_remise_add = remise_add
                    best_labo = coverage

            if best_labo and best_remise_add > 0:
                selected_labos.append(best_labo)
                ventes_couvertes |= best_labo.ventes_couvertes
                montant_remise_total += best_remise_add
            else:
                break  # Plus de labo interessant

        # Calculer stats finales
        chiffre_realise = sum(
            ventes_map[vid].montant_annuel or Decimal("0")
            for vid in ventes_couvertes
        )
        couverture_pct = float(chiffre_realise) / float(chiffre_total) * 100 if chiffre_total > 0 else 0

        return ComboResult(
            labos=selected_labos,
            couverture_totale_pct=round(couverture_pct, 1),
            chiffre_total_realise=chiffre_realise,
            montant_remise_total=montant_remise_total,
            ventes_non_couvertes=set(vente_ids) - ventes_couvertes
        )

    def compare_all_single_labos(
        self,
        import_id: int
    ) -> List[Tuple[LaboCoverage, Decimal]]:
        """
        Compare tous les labos en solo.

        Retourne une liste triee par montant de remise decroissant.
        Utile pour choisir le meilleur labo principal.
        """
        # Recuperer toutes les ventes
        ventes = self.db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
        if not ventes:
            return []

        vente_ids = [v.id for v in ventes]
        ventes_map = {v.id: v for v in ventes}

        # Recuperer tous les labos actifs
        labos = self.db.query(Laboratoire).filter(Laboratoire.actif == True).all()

        results = []
        for labo in labos:
            coverage = self.calculate_lab_coverage(labo.id, vente_ids, ventes_map)
            remise = self.estimate_remise(coverage)
            results.append((coverage, remise))

        # Trier par montant de remise decroissant
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def get_complementarity_matrix(
        self,
        import_id: int
    ) -> Dict[str, any]:
        """
        Calcule une matrice de complementarite entre labos.

        Pour chaque paire de labos:
        - Overlap: produits couverts par les deux
        - Unique A: produits couverts seulement par A
        - Unique B: produits couverts seulement par B
        - Combo coverage: produits couverts par A ou B

        Utile pour visualiser quelle combo est la plus interessante.
        """
        # Recuperer toutes les ventes
        ventes = self.db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
        if not ventes:
            return {"error": "Aucune vente"}

        vente_ids = [v.id for v in ventes]
        ventes_map = {v.id: v for v in ventes}
        chiffre_total = sum(v.montant_annuel or Decimal("0") for v in ventes)

        # Recuperer tous les labos actifs
        labos = self.db.query(Laboratoire).filter(Laboratoire.actif == True).all()

        # Calculer couverture de chaque labo
        coverages = {}
        for labo in labos:
            coverages[labo.id] = self.calculate_lab_coverage(labo.id, vente_ids, ventes_map)

        # Matrice de complementarite
        matrix = []
        for i, labo_a in enumerate(labos):
            cov_a = coverages[labo_a.id]
            for labo_b in labos[i+1:]:
                cov_b = coverages[labo_b.id]

                overlap = cov_a.ventes_couvertes & cov_b.ventes_couvertes
                unique_a = cov_a.ventes_couvertes - cov_b.ventes_couvertes
                unique_b = cov_b.ventes_couvertes - cov_a.ventes_couvertes
                combo = cov_a.ventes_couvertes | cov_b.ventes_couvertes

                montant_combo = sum(ventes_map[vid].montant_annuel or Decimal("0") for vid in combo)
                couverture_combo = float(montant_combo) / float(chiffre_total) * 100 if chiffre_total > 0 else 0

                # Estimer remise combo (somme des remises individuelles sur leurs uniques)
                remise_a = self.estimate_remise(LaboCoverage(
                    labo_id=labo_a.id,
                    labo_nom=labo_a.nom,
                    remise_negociee=labo_a.remise_negociee or Decimal("0"),
                    ventes_couvertes=unique_a | overlap,  # A couvre overlap
                    montant_couvert=sum(ventes_map[vid].montant_annuel or Decimal("0") for vid in (unique_a | overlap)),
                    nb_produits=len(unique_a | overlap)
                ))
                remise_b = self.estimate_remise(LaboCoverage(
                    labo_id=labo_b.id,
                    labo_nom=labo_b.nom,
                    remise_negociee=labo_b.remise_negociee or Decimal("0"),
                    ventes_couvertes=unique_b,  # B ne couvre que ses uniques
                    montant_couvert=sum(ventes_map[vid].montant_annuel or Decimal("0") for vid in unique_b),
                    nb_produits=len(unique_b)
                ))

                matrix.append({
                    "labo_a_id": labo_a.id,
                    "labo_a_nom": labo_a.nom,
                    "labo_b_id": labo_b.id,
                    "labo_b_nom": labo_b.nom,
                    "overlap_count": len(overlap),
                    "unique_a_count": len(unique_a),
                    "unique_b_count": len(unique_b),
                    "combo_count": len(combo),
                    "couverture_combo_pct": round(couverture_combo, 1),
                    "montant_combo_ht": float(montant_combo),
                    "remise_combo_estimee": float(remise_a + remise_b)
                })

        # Trier par remise combo decroissante
        matrix.sort(key=lambda x: x["remise_combo_estimee"], reverse=True)

        return {
            "total_ventes": len(ventes),
            "chiffre_total_ht": float(chiffre_total),
            "matrix": matrix
        }
