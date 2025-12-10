from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Computed,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Laboratoire(Base):
    """Table des laboratoires generiques."""
    __tablename__ = "laboratoires"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False, unique=True)
    remise_negociee = Column(Numeric(5, 2), nullable=True)  # % remise remontee negociee
    remise_ligne_defaut = Column(Numeric(5, 2), nullable=True)  # % remise ligne par defaut
    actif = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    catalogue = relationship("CatalogueProduit", back_populates="laboratoire", cascade="all, delete-orphan")
    regles_remontee = relationship("RegleRemontee", back_populates="laboratoire", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="laboratoire")


class Presentation(Base):
    """Table des presentations (referentiel commun = CODE INTERNE)."""
    __tablename__ = "presentations"

    id = Column(Integer, primary_key=True, index=True)
    code_interne = Column(String(50), nullable=False, unique=True, index=True)  # Ex: "FURO-40-30"
    molecule = Column(String(200), nullable=False, index=True)  # "Furosemide"
    dosage = Column(String(50), nullable=True)  # "40mg"
    forme = Column(String(50), nullable=True)  # "comprime"
    conditionnement = Column(Integer, nullable=True)  # 30
    type_conditionnement = Column(String(20), nullable=True)  # "petit" ou "grand"
    classe_therapeutique = Column(String(100), nullable=True)  # Pour V2
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    produits = relationship("CatalogueProduit", back_populates="presentation")
    ventes = relationship("MesVentes", back_populates="presentation")
    resultats = relationship("ResultatSimulation", back_populates="presentation")


class CatalogueProduit(Base):
    """Table des produits par laboratoire (catalogue)."""
    __tablename__ = "catalogue_produits"
    __table_args__ = (
        UniqueConstraint("laboratoire_id", "code_cip", name="uq_labo_cip"),
    )

    id = Column(Integer, primary_key=True, index=True)
    laboratoire_id = Column(Integer, ForeignKey("laboratoires.id", ondelete="CASCADE"), nullable=False)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=True)
    code_cip = Column(String(20), nullable=True, index=True)  # Code CIP officiel
    code_acl = Column(String(20), nullable=True)  # Code ACL si different
    nom_commercial = Column(String(200), nullable=True)  # "Furosemide Viatris 40mg Cpr B/30"
    prix_ht = Column(Numeric(10, 2), nullable=True)  # Prix d'achat HT
    remise_pct = Column(Numeric(5, 2), nullable=True)  # % remise de cette ligne
    # Gestion remontee:
    # NULL = remontee normale (% negocie du labo)
    # 0 = exclu (pas de remontee)
    # X = remontee partielle a X%
    remontee_pct = Column(Numeric(5, 2), nullable=True)
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    laboratoire = relationship("Laboratoire", back_populates="catalogue")
    presentation = relationship("Presentation", back_populates="produits")
    resultats = relationship("ResultatSimulation", back_populates="produit")


class RegleRemontee(Base):
    """Table des regles de remontee (exclusions, partielles)."""
    __tablename__ = "regles_remontee"

    id = Column(Integer, primary_key=True, index=True)
    laboratoire_id = Column(Integer, ForeignKey("laboratoires.id", ondelete="CASCADE"), nullable=False)
    nom_regle = Column(String(100), nullable=False)  # "Exclusions Zentiva 2024"
    type_regle = Column(String(20), nullable=False)  # 'exclusion' ou 'partielle'
    remontee_pct = Column(Numeric(5, 2), nullable=False)  # 0 pour exclusion, ou % partiel
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    laboratoire = relationship("Laboratoire", back_populates="regles_remontee")
    produits = relationship("RegleRemonteeProduit", back_populates="regle", cascade="all, delete-orphan")


class RegleRemonteeProduit(Base):
    """Table de liaison regles - produits."""
    __tablename__ = "regles_remontee_produits"
    __table_args__ = (
        UniqueConstraint("regle_id", "produit_id", name="uq_regle_produit"),
    )

    id = Column(Integer, primary_key=True, index=True)
    regle_id = Column(Integer, ForeignKey("regles_remontee.id", ondelete="CASCADE"), nullable=False)
    produit_id = Column(Integer, ForeignKey("catalogue_produits.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    regle = relationship("RegleRemontee", back_populates="produits")
    produit = relationship("CatalogueProduit")


class MesVentes(Base):
    """Table de mes ventes (historique pharmacie importe)."""
    __tablename__ = "mes_ventes"

    id = Column(Integer, primary_key=True, index=True)
    import_id = Column(Integer, ForeignKey("imports.id"), nullable=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=True)
    code_cip_achete = Column(String(20), nullable=True)  # CIP du produit achete
    labo_actuel = Column(String(100), nullable=True)  # Nom labo actuel
    designation = Column(String(200), nullable=True)  # Nom complet produit
    quantite_annuelle = Column(Integer, nullable=True)
    prix_achat_unitaire = Column(Numeric(10, 2), nullable=True)
    montant_annuel = Column(Numeric(12, 2), nullable=True)  # Calcule: quantite * prix
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    presentation = relationship("Presentation", back_populates="ventes")
    import_obj = relationship("Import", back_populates="ventes")


class Import(Base):
    """Table des historiques d'import."""
    __tablename__ = "imports"

    id = Column(Integer, primary_key=True, index=True)
    type_import = Column(String(50), nullable=False)  # 'catalogue' ou 'ventes'
    nom_fichier = Column(String(200), nullable=True)
    laboratoire_id = Column(Integer, ForeignKey("laboratoires.id"), nullable=True)
    nb_lignes_importees = Column(Integer, nullable=True)
    nb_lignes_erreur = Column(Integer, nullable=True)
    statut = Column(String(20), default="en_cours")  # 'en_cours', 'termine', 'erreur'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    ventes = relationship("MesVentes", back_populates="import_obj")


class CorrespondanceManuelle(Base):
    """Table des correspondances manuelles (click-to-match)."""
    __tablename__ = "correspondances_manuelles"
    __table_args__ = (
        UniqueConstraint("presentation_id", "produit_id", name="uq_presentation_produit"),
    )

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    produit_id = Column(Integer, ForeignKey("catalogue_produits.id"), nullable=False)
    cree_par = Column(String(100), nullable=True)  # Utilisateur qui a fait le match
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Scenario(Base):
    """Table des scenarios de simulation."""
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    laboratoire_id = Column(Integer, ForeignKey("laboratoires.id"), nullable=False)
    remise_simulee = Column(Numeric(5, 2), nullable=True)  # % remise pour ce scenario
    import_ventes_id = Column(Integer, ForeignKey("imports.id"), nullable=True)  # Ventes utilisees
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    laboratoire = relationship("Laboratoire", back_populates="scenarios")
    resultats = relationship("ResultatSimulation", back_populates="scenario", cascade="all, delete-orphan")


class ResultatSimulation(Base):
    """Table des resultats de simulation (cache pour perfs)."""
    __tablename__ = "resultats_simulation"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=True)
    quantite = Column(Integer, nullable=True)
    montant_ht = Column(Numeric(12, 2), nullable=True)  # Montant HT des achats
    disponible = Column(Boolean, default=False)  # Produit disponible chez le labo?
    produit_id = Column(Integer, ForeignKey("catalogue_produits.id"), nullable=True)  # Produit trouve
    remise_ligne = Column(Numeric(5, 2), nullable=True)  # % remise sur ligne
    montant_remise_ligne = Column(Numeric(12, 2), nullable=True)  # Gain remise ligne
    statut_remontee = Column(String(20), nullable=True)  # 'normal', 'partiel', 'exclu', 'indisponible'
    remontee_cible = Column(Numeric(5, 2), nullable=True)  # % cible de remontee
    montant_remontee = Column(Numeric(12, 2), nullable=True)  # Complement remontee
    remise_totale = Column(Numeric(5, 2), nullable=True)  # % remise totale
    montant_total_remise = Column(Numeric(12, 2), nullable=True)  # Gain total
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    scenario = relationship("Scenario", back_populates="resultats")
    presentation = relationship("Presentation", back_populates="resultats")
    produit = relationship("CatalogueProduit", back_populates="resultats")


class Parametre(Base):
    """Table des parametres globaux."""
    __tablename__ = "parametres"

    cle = Column(String(50), primary_key=True)
    valeur = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
