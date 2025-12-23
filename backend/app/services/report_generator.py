"""Generateur de rapports PDF avec graphiques.

Utilise ReportLab pour la generation PDF et Matplotlib pour les graphiques.

Structure du rapport:
1. Page de garde avec resume
2. Graphique camembert: couverture (realise vs perdu)
3. Graphique barres: comparaison remises par type
4. Graphique barres: comparaison labos complementaires
5. Tableau des produits non couverts (top 20)
6. Recommandation combo optimale
"""
import io
import base64
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Any

import matplotlib
matplotlib.use('Agg')  # Backend sans GUI
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def format_euro(value: Decimal | float) -> str:
    """Formate un montant en euros."""
    if isinstance(value, Decimal):
        value = float(value)
    return f"{value:,.2f} EUR".replace(",", " ").replace(".", ",")


def format_pct(value: float) -> str:
    """Formate un pourcentage."""
    return f"{value:.1f}%"


class ChartGenerator:
    """Generateur de graphiques pour le rapport."""

    @staticmethod
    def create_coverage_pie(
        chiffre_realise: float,
        chiffre_perdu: float
    ) -> bytes:
        """
        Cree un camembert de couverture.

        Returns:
            Image PNG en bytes
        """
        fig, ax = plt.subplots(figsize=(5, 4))

        sizes = [chiffre_realise, chiffre_perdu]
        labels = [
            f'Realisable\n{format_euro(chiffre_realise)}',
            f'Perdu\n{format_euro(chiffre_perdu)}'
        ]
        colors_pie = ['#4CAF50', '#F44336']  # Vert, Rouge
        explode = (0.02, 0.02)

        wedges, texts, autotexts = ax.pie(
            sizes,
            explode=explode,
            labels=labels,
            colors=colors_pie,
            autopct='%1.1f%%',
            shadow=False,
            startangle=90
        )

        # Style des textes
        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')

        ax.set_title('Couverture du Catalogue', fontsize=12, fontweight='bold')
        ax.axis('equal')

        # Convertir en bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    @staticmethod
    def create_remise_bars(
        remise_ligne: float,
        remontee: float,
        total: float
    ) -> bytes:
        """
        Cree un graphique barres des remises.

        Returns:
            Image PNG en bytes
        """
        fig, ax = plt.subplots(figsize=(6, 4))

        categories = ['Remise Facture', 'Remontee', 'Total']
        values = [remise_ligne, remontee, total]
        colors_bar = ['#2196F3', '#FF9800', '#4CAF50']

        bars = ax.bar(categories, values, color=colors_bar, edgecolor='white', linewidth=1.2)

        # Ajouter les valeurs sur les barres
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(
                format_euro(val),
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom',
                fontsize=9, fontweight='bold'
            )

        ax.set_ylabel('Montant (EUR)', fontsize=10)
        ax.set_title('Decomposition des Remises', fontsize=12, fontweight='bold')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Convertir en bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    @staticmethod
    def create_labos_comparison(
        labos_data: List[Dict]
    ) -> bytes:
        """
        Cree un graphique barres horizontales comparant les labos.

        Args:
            labos_data: Liste de dicts avec 'nom', 'chiffre_recupere', 'remise_estimee'

        Returns:
            Image PNG en bytes
        """
        if not labos_data:
            # Graphique vide
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.text(0.5, 0.5, 'Aucun labo complementaire', ha='center', va='center')
            ax.axis('off')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()

        fig, ax = plt.subplots(figsize=(8, max(3, len(labos_data) * 0.5 + 1)))

        noms = [d['nom'] for d in labos_data]
        remises = [float(d['remise_estimee']) for d in labos_data]

        y_pos = range(len(noms))
        colors_bar = plt.cm.Blues([(i + 3) / (len(noms) + 5) for i in range(len(noms))])

        bars = ax.barh(y_pos, remises, color=colors_bar, edgecolor='white', linewidth=1)

        # Ajouter les valeurs
        for bar, val in zip(bars, remises):
            width = bar.get_width()
            ax.annotate(
                format_euro(val),
                xy=(width, bar.get_y() + bar.get_height() / 2),
                xytext=(5, 0),
                textcoords="offset points",
                ha='left', va='center',
                fontsize=9
            )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(noms)
        ax.invert_yaxis()
        ax.set_xlabel('Montant Remise Estimee (EUR)', fontsize=10)
        ax.set_title('Comparaison Labos Complementaires', fontsize=12, fontweight='bold')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Convertir en bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()


class PDFReportGenerator:
    """Generateur de rapport PDF."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        self.chart_gen = ChartGenerator()

    def _setup_styles(self):
        """Configure les styles personnalises."""
        self.styles.add(ParagraphStyle(
            name='TitleMain',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        self.styles.add(ParagraphStyle(
            name='SubTitle',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.grey,
            spaceAfter=20,
            alignment=TA_CENTER
        ))
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading1'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#1976D2')
        ))
        self.styles.add(ParagraphStyle(
            name='KeyValue',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=16
        ))
        self.styles.add(ParagraphStyle(
            name='BigNumber',
            parent=self.styles['Normal'],
            fontSize=20,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#4CAF50'),
            alignment=TA_CENTER
        ))

    def _create_summary_table(self, totaux: Dict) -> Table:
        """Cree le tableau de resume."""
        data = [
            ['Chiffre Total HT', format_euro(totaux.get('chiffre_total_ht', 0))],
            ['Chiffre Realisable', format_euro(totaux.get('chiffre_realisable_ht', 0))],
            ['Chiffre Perdu', format_euro(totaux.get('chiffre_perdu_ht', 0))],
            ['', ''],
            ['Remise Facture', format_euro(totaux.get('total_remise_ligne', 0))],
            ['Remontee', format_euro(totaux.get('total_remontee', 0))],
            ['TOTAL REMISES', format_euro(totaux.get('total_remise_globale', 0))],
            ['', ''],
            ['Taux de Couverture', format_pct(float(totaux.get('taux_couverture', 0)))],
            ['Remise Moyenne', format_pct(float(totaux.get('remise_totale_ponderee', 0)))],
        ]

        table = Table(data, colWidths=[6*cm, 4*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 6), (0, 6), 'Helvetica-Bold'),  # TOTAL REMISES
            ('FONTSIZE', (0, 6), (-1, 6), 12),
            ('TEXTCOLOR', (1, 6), (1, 6), colors.HexColor('#4CAF50')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 2), (-1, 2), 0.5, colors.lightgrey),
            ('LINEBELOW', (0, 6), (-1, 6), 1, colors.HexColor('#4CAF50')),
        ]))
        return table

    def _create_products_table(self, products: List[Dict], title: str = "Produits Non Couverts") -> List:
        """Cree le tableau des produits."""
        elements = []
        elements.append(Paragraph(title, self.styles['SectionTitle']))

        if not products:
            elements.append(Paragraph("Aucun produit non couvert.", self.styles['Normal']))
            return elements

        # Header
        data = [['Designation', 'Montant HT', 'Alternative']]

        for p in products[:20]:  # Max 20
            alternative = "Aucune"
            if p.get('alternatives') and len(p['alternatives']) > 0:
                alt = p['alternatives'][0]
                alternative = f"{alt.get('labo_nom', '?')} ({format_pct(alt.get('remise_negociee', 0))})"

            data.append([
                p.get('designation', '')[:50],  # Tronquer
                format_euro(p.get('montant_annuel', 0)),
                alternative
            ])

        table = Table(data, colWidths=[8*cm, 3*cm, 5*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E3F2FD')),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(table)
        return elements

    def generate_simulation_report(
        self,
        labo_nom: str,
        totaux: Dict,
        recommendations: List[Dict],
        gaps: List[Dict],
        best_combo: Optional[Dict] = None,
        pharmacie_nom: str = "Ma Pharmacie"
    ) -> bytes:
        """
        Genere le rapport PDF complet.

        Args:
            labo_nom: Nom du laboratoire principal
            totaux: Dictionnaire des totaux (TotauxSimulation)
            recommendations: Liste des labos complementaires recommandes
            gaps: Liste des produits non couverts
            best_combo: Info sur la meilleure combinaison
            pharmacie_nom: Nom de la pharmacie

        Returns:
            Contenu PDF en bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        elements = []

        # ===== PAGE DE GARDE =====
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph("RAPPORT DE SIMULATION", self.styles['TitleMain']))
        elements.append(Paragraph(f"Remises {labo_nom}", self.styles['SubTitle']))
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph(
            f"Pharmacie: {pharmacie_nom}<br/>Date: {datetime.now().strftime('%d/%m/%Y')}",
            self.styles['Normal']
        ))
        elements.append(Spacer(1, 2*cm))

        # Resume des chiffres cles
        elements.append(Paragraph("Resume", self.styles['SectionTitle']))
        elements.append(self._create_summary_table(totaux))
        elements.append(Spacer(1, 1*cm))

        # ===== GRAPHIQUE COUVERTURE =====
        elements.append(Paragraph("Couverture du Catalogue", self.styles['SectionTitle']))

        pie_data = self.chart_gen.create_coverage_pie(
            float(totaux.get('chiffre_realisable_ht', 0)),
            float(totaux.get('chiffre_perdu_ht', 0))
        )
        pie_image = Image(io.BytesIO(pie_data), width=10*cm, height=8*cm)
        elements.append(pie_image)
        elements.append(Spacer(1, 1*cm))

        # ===== GRAPHIQUE REMISES =====
        elements.append(Paragraph("Decomposition des Remises", self.styles['SectionTitle']))

        bar_data = self.chart_gen.create_remise_bars(
            float(totaux.get('total_remise_ligne', 0)),
            float(totaux.get('total_remontee', 0)),
            float(totaux.get('total_remise_globale', 0))
        )
        bar_image = Image(io.BytesIO(bar_data), width=12*cm, height=8*cm)
        elements.append(bar_image)

        elements.append(PageBreak())

        # ===== LABOS COMPLEMENTAIRES =====
        if recommendations:
            elements.append(Paragraph("Labos Complementaires", self.styles['SectionTitle']))
            elements.append(Paragraph(
                f"Pour le chiffre perdu ({format_euro(totaux.get('chiffre_perdu_ht', 0))}), "
                "voici les alternatives classees par montant de remise:",
                self.styles['Normal']
            ))
            elements.append(Spacer(1, 0.5*cm))

            labos_chart_data = [
                {
                    'nom': r.get('lab_nom', '?'),
                    'chiffre_recupere': r.get('chiffre_recupere_ht', 0),
                    'remise_estimee': r.get('montant_remise_estime', 0)
                }
                for r in recommendations[:8]
            ]

            comp_chart = self.chart_gen.create_labos_comparison(labos_chart_data)
            comp_image = Image(io.BytesIO(comp_chart), width=14*cm, height=6*cm)
            elements.append(comp_image)
            elements.append(Spacer(1, 1*cm))

            # Tableau detaille
            reco_data = [['Labo', 'Chiffre Recupere', 'Remise Estimee', 'Couverture Add.']]
            for r in recommendations[:10]:
                reco_data.append([
                    r.get('lab_nom', '?'),
                    format_euro(r.get('chiffre_recupere_ht', 0)),
                    format_euro(r.get('montant_remise_estime', 0)),
                    format_pct(r.get('couverture_additionnelle_pct', 0))
                ])

            reco_table = Table(reco_data, colWidths=[4*cm, 4*cm, 4*cm, 3*cm])
            reco_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E3F2FD')),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(reco_table)

        # ===== BEST COMBO =====
        if best_combo:
            elements.append(Spacer(1, 1*cm))
            elements.append(Paragraph("Recommandation", self.styles['SectionTitle']))

            combo_labs = " + ".join([l.get('nom', '?') for l in best_combo.get('labs', [])])
            elements.append(Paragraph(
                f"<b>Combo Optimale:</b> {combo_labs}",
                self.styles['KeyValue']
            ))
            elements.append(Paragraph(
                f"<b>Couverture Totale:</b> {format_pct(best_combo.get('couverture_totale_pct', 0))}",
                self.styles['KeyValue']
            ))
            elements.append(Paragraph(
                f"<b>Chiffre Realisable:</b> {format_euro(best_combo.get('chiffre_total_realisable_ht', 0))}",
                self.styles['KeyValue']
            ))
            elements.append(Paragraph(
                f"<b>Remises Totales:</b> {format_euro(best_combo.get('montant_remise_total', 0))}",
                self.styles['BigNumber']
            ))

        elements.append(PageBreak())

        # ===== PRODUITS NON COUVERTS =====
        if gaps:
            elements.extend(self._create_products_table(gaps, "Top 20 Produits Non Couverts"))

        # ===== FOOTER =====
        elements.append(Spacer(1, 2*cm))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        elements.append(Paragraph(
            f"Rapport genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} - Pharma Remises",
            ParagraphStyle('Footer', fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
        ))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()


# Fonction utilitaire pour usage direct
def generate_pdf_report(
    labo_nom: str,
    totaux: Dict,
    recommendations: List[Dict] = None,
    gaps: List[Dict] = None,
    best_combo: Dict = None,
    pharmacie_nom: str = "Ma Pharmacie"
) -> bytes:
    """
    Fonction utilitaire pour generer un rapport PDF.

    Args:
        labo_nom: Nom du labo principal
        totaux: Totaux de la simulation
        recommendations: Labos complementaires
        gaps: Produits non couverts
        best_combo: Meilleure combinaison
        pharmacie_nom: Nom de la pharmacie

    Returns:
        PDF en bytes
    """
    generator = PDFReportGenerator()
    return generator.generate_simulation_report(
        labo_nom=labo_nom,
        totaux=totaux,
        recommendations=recommendations or [],
        gaps=gaps or [],
        best_combo=best_combo,
        pharmacie_nom=pharmacie_nom
    )
