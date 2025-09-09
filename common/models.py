from django.db import models
from common.mixins import AuditMixin

class Pages(AuditMixin):
    TYPE_CHOICES = [
        ("VENTE", "Vente"),
        ("SERVICE", "Service"),
    ]
    
    nom = models.CharField(max_length=100)
    contact = models.CharField(max_length=100)
    lien = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default="VENTE"
    )

    def __str__(self):
        return self.nom

class Caisse(AuditMixin):
    nom = models.CharField(max_length=100)
    responsable = models.CharField(max_length=100)
    solde_initial = models.PositiveIntegerField(default=0)
    entree = models.PositiveIntegerField(default=0)
    sortie = models.PositiveIntegerField(default=0)
    solde = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nom

class PlanDesComptes(AuditMixin):
    compte_numero = models.CharField(max_length=20)
    libelle = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.compte_numero} - {self.libelle}"
