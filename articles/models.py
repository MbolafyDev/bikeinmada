from django.db import models
from django.utils.text import slugify
from common.mixins import AuditMixin


class Categorie(AuditMixin):
    categorie = models.CharField("Categorie", max_length=100)

    def __str__(self):
        return self.categorie


class Taille(AuditMixin):
    taille = models.CharField("Taille", max_length=100)

    def __str__(self):
        return self.taille


class Couleur(AuditMixin):
    couleur = models.CharField("Couleur", max_length=100)

    def __str__(self):
        return self.couleur


class Article(AuditMixin):
    LIVRAISON_CHOICES = [
        ('Payante', 'Payante'),
        ('Gratuite', 'Gratuite'),
    ]

    nom = models.CharField("Nom de l'article", max_length=100)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    reference = models.CharField("Référence", max_length=50, unique=True, blank=True)
    prix_achat = models.PositiveIntegerField("Prix d'achat (Ar)")
    prix_vente = models.PositiveIntegerField("Prix de vente (Ar)")
    livraison = models.CharField(
        "Frais de livraison",
        max_length=10,
        choices=LIVRAISON_CHOICES,
        default='Payante'
    )

    # ✅ Corrections ici
    taille = models.ForeignKey('Taille', on_delete=models.SET_NULL, blank=True, null=True)
    couleur = models.ForeignKey('Couleur', on_delete=models.SET_NULL, blank=True, null=True)
    categorie = models.ForeignKey('Categorie', on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        # Si pas de référence fournie → slug du nom
        if not self.reference:
            base_slug = slugify(self.nom)
            unique_slug = base_slug
            num = 1
            # Vérifier unicité
            while Article.objects.filter(reference=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.reference = unique_slug
        super().save(*args, **kwargs)

    @property
    def stock_final(self):
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
