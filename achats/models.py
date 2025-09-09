from django.db import models
from articles.models import Article 
from common.models import Caisse
from common.mixins import AuditMixin

class Achat(AuditMixin):
    date = models.DateField("Date d'achat")  # date saisie manuellement
    num_facture = models.TextField("N° Facture", blank=True, null=True)
    remarque = models.TextField("Remarque", blank=True, null=True)
    paiement = models.ForeignKey(Caisse, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Achat du {self.date}"

    @property
    def total(self):
        return sum(ligne.montant for ligne in self.lignes_achats.all())

class LigneAchat(AuditMixin):
    achat = models.ForeignKey(Achat, on_delete=models.CASCADE, related_name="lignes_achats")
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="lignes_achats")
    pu = models.PositiveIntegerField("Prix Unitaire (Ar)")
    quantite = models.PositiveIntegerField("Quantité")
    montant = models.PositiveIntegerField("Montant total (Ar)")

    def total_ligne(self):
        return self.pu * self.quantite

    def save(self, *args, **kwargs):
        self.montant = self.pu * self.quantite
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.article.nom} x {self.quantite} (PU: {self.pu})"
