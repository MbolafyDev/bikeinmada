from django.db import models
from common.models import Pages, Caisse
from django.utils.timezone import now
from common.mixins import AuditMixin

class Versement(AuditMixin):
    date = models.DateField(default=now)
    montant = models.PositiveIntegerField()
    page = models.ForeignKey(Pages, on_delete=models.SET_NULL, null=True)
    remarque = models.CharField(max_length=255, blank=True)
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE)

    def __str__(self):
        return f"Versement {self.date} - {self.caisse.nom}"

class MouvementCaisse(AuditMixin):
    date = models.DateField(default=now)
    caisse_debit = models.ForeignKey(Caisse, related_name='mouvements_sortie', on_delete=models.CASCADE)
    caisse_credit = models.ForeignKey(Caisse, related_name='mouvements_entree', on_delete=models.CASCADE)
    montant = models.PositiveIntegerField()
    reference = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.date.date()} - {self.montant} Ar de {self.caisse_debit} à {self.caisse_credit}"