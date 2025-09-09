from django.db import models
from common.mixins import AuditMixin

class Article(AuditMixin):
    LIVRAISON_CHOICES = [
        ('Payante', 'Payante'),
        ('Gratuite', 'Gratuite'),
    ]

    nom = models.CharField("Nom de l'article", max_length=100)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    reference = models.CharField("Référence", max_length=50, unique=True)
    prix_achat = models.PositiveIntegerField("Prix d'achat (Ar)")
    prix_vente = models.PositiveIntegerField("Prix de vente (Ar)")
    livraison = models.CharField(
        "Frais de livraison",
        max_length=10,
        choices=LIVRAISON_CHOICES,
        default='Payante'
    )

    def __str__(self):
        return self.nom

    @property
    def stock_final(self):
        # Import local pour éviter les import circulaires
        from achats.models import LigneAchat
        from ventes.models import LigneCommande
        from stocks.models import Inventaire

        entrees = sum(
            ligne.quantite
            for ligne in self.lignes_achats.filter(achat__statut_publication__iexact="publiée")
        )
        sorties = sum(
            ligne.quantite
            for ligne in self.lignes_commandes.filter(
                commande__statut_publication__iexact="publiée"
            ).exclude(commande__statut_vente="Annulée")
        )
        ajustements = sum(
            inv.ajustement
            for inv in self.inventaires.filter(statut_publication__iexact="publiée")
        )
        return entrees - sorties + ajustements

class Service(AuditMixin):
    nom = models.CharField("Nom de l'article", max_length=100)
    reference = models.CharField("Référence", max_length=50, unique=True)
    tarif = models.PositiveIntegerField("Tarif (Ar)")

    def __str__(self):
        return self.nom