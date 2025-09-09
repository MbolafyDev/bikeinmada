from django.db import models
from common.models import PlanDesComptes, Caisse, Pages
from common.mixins import AuditMixin

class Charge(AuditMixin):
    date = models.DateField()
    libelle = models.ForeignKey(PlanDesComptes, on_delete=models.PROTECT)
    pu = models.PositiveIntegerField("Prix unitaire")
    quantite = models.PositiveIntegerField("Quantité")
    montant = models.PositiveIntegerField()
    remarque = models.CharField(max_length=255, blank=True)
    paiement = models.ForeignKey(Caisse, on_delete=models.PROTECT)
    page = models.ForeignKey(Pages, null=True, blank=True, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.date} - {self.libelle.libelle}"
