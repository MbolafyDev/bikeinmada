from django.db import models
from common.mixins import AuditMixin

class Livreur(AuditMixin):
    TYPE_CHOICES = [
        ('Employé', 'Employé'),
        ('Prestataire', 'Prestataire'),
    ]

    nom = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Employé')
    responsable = models.CharField(max_length=100)
    adresse = models.CharField(max_length=255)
    contact = models.CharField(max_length=50)

    def __str__(self):
        return self.nom

CATEGORIE_CHOIX = [
    ('Ville', 'Ville'),
    ('Périphérie', 'Périphérie'),
    ('Super-périphérie', 'Super-périphérie'),
    ('Province', 'Province'),
]

FRAIS_PAR_DEFAUT = {
    'Ville': 4000,
    'Périphérie': 5000,
    'Super-périphérie': 6000,
    'Province': 4000,
}

class Livraison(AuditMixin):
    lieu = models.CharField(max_length=100)
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOIX)
    frais = models.PositiveIntegerField()

    def save(self, *args, **kwargs):
        if not self.frais:
            self.frais = FRAIS_PAR_DEFAUT.get(self.categorie, 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.lieu} - {self.categorie} : {self.frais} Ar"
