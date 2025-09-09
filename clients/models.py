from django.db import models
from django.utils import timezone
from livraison.models import Livraison
from common.mixins import AuditMixin

class Client(AuditMixin):
    nom = models.CharField(max_length=100)
    lieu = models.ForeignKey(Livraison, on_delete=models.SET_NULL, null=True)
    precision_lieu = models.CharField(max_length=255, blank=True, null=True)
    contact = models.CharField(max_length=50)

    def __str__(self):
        return self.nom

class Entreprise(AuditMixin):
    raison_sociale = models.CharField(max_length=255)
    date_debut = models.DateField(default=timezone.now, null=True, blank=True)
    page_facebook = models.CharField(max_length=255, blank=True, null=True)
    lien_page = models.URLField(blank=True, null=True)
    activite_produits = models.CharField(max_length=255, blank=True, null=True)
    personne_de_contact = models.CharField(max_length=255, blank=True, null=True)
    lien_profil = models.URLField(blank=True, null=True)
    nif = models.CharField(max_length=50, blank=True, null=True)
    stat = models.CharField(max_length=50, blank=True, null=True)
    rcs = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    fokontany = models.CharField(max_length=255, blank=True, null=True)
    commune = models.CharField(max_length=255, blank=True, null=True)
    region = models.CharField(max_length=255, blank=True, null=True)
    cin_numero = models.CharField(max_length=50, blank=True, null=True)
    date_cin = models.DateField(blank=True, null=True)
    lieu_cin = models.CharField(max_length=255, blank=True, null=True)
    remarque = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.raison_sociale
