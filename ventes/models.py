from django.db import models, transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
import time
from typing import Optional
import re

from clients.models import Client
from articles.models import Article
from common.models import Pages, Caisse
from livraison.models import Livreur
from common.constants import ETAT_CHOIX
from common.mixins import AuditMixin  

FRAIS_LIVREUR_CHOIX = [
    ('Payée', 'Payée'),
    ('Non payée', 'Non payée'),
    ('N/A', 'N/A'),
]

class Commande(AuditMixin):   
    numero_facture = models.CharField(max_length=20, unique=True, editable=False)
    date_commande = models.DateField(default=timezone.now)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    page = models.ForeignKey(Pages, null=True, default=1, on_delete=models.SET_NULL, related_name="ventes_commandes")
    remarque = models.TextField(blank=True, null=True)
    
    statut_vente = models.CharField(max_length=20, choices=ETAT_CHOIX, default='En attente')
    statut_livraison = models.CharField(max_length=20, choices=ETAT_CHOIX, default='En attente')
    
    frais_livraison = models.PositiveIntegerField(null=True, blank=True,default=0)
    date_livraison = models.DateField(null=True, blank=True, default=timezone.now)
    date_debut_prestation = models.DateField(null=True, blank=True, default=timezone.now)
    date_fin_prestation = models.DateField(null=True, blank=True, default=timezone.now)

    livreur = models.ForeignKey(Livreur, null=True, blank=True, on_delete=models.SET_NULL)
    frais_livreur = models.PositiveIntegerField(null=True, blank=True,default=0)
    paiement_frais_livreur = models.CharField(
        max_length=15,
        choices=FRAIS_LIVREUR_CHOIX,
        default='Non payée'
    )
    cours_devise = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Facture {self.numero_facture} - {self.client.nom}"
    
    @property
    def montant_commande(self):
        return sum(ligne.montant() for ligne in self.lignes_commandes.all()) 
 
    def total_commande(self):
        return self.montant_commande + (self.frais_livraison or 0)

    def save(self, *args, **kwargs):
        max_attempts = 5
        for attempt in range(max_attempts):
            if not self.numero_facture:
                self.numero_facture = self.__class__.generer_numero_facture_atomic()
            try:
                super().save(*args, **kwargs)
                break  # Success
            except IntegrityError as e:
                if "Duplicate entry" in str(e):
                    time.sleep(0.1)  # backoff léger
                    self.numero_facture = None  # forcer la régénération
                    continue
                raise
        else:
            raise IntegrityError("Impossible de générer un numero_facture unique après plusieurs tentatives")

    # Désactiver la modification selon les statuts 
    def actions_desactivees(self):
        return (
            self.statut_vente in ["Payée", "Annulée", "Reportée", "Supprimée"]
            or self.statut_livraison in ["Livrée", "Annulée", "Reportée", "Supprimée"]
        )
    
    def duree_prestation(self) -> Optional[int]:
        d1 = self.date_debut_prestation
        d2 = self.date_fin_prestation
        if not d1 or not d2:
            return None
        if d2 < d1:
            return 0
        return (d2 - d1).days + 1

    def clean(self):
        super().clean()
        if self.date_debut_prestation and self.date_fin_prestation:
            if self.date_fin_prestation < self.date_debut_prestation:
                raise ValidationError({
                    "date_fin_prestation": "La date de fin ne peut pas être avant la date de début."
                })
    
    @classmethod
    def generer_numero_facture_atomic(cls, prefix: str = "bim", serie: str = "B", padding: int = 3) -> str:
        with transaction.atomic():
            date_str = timezone.now().strftime("%y%m")
            full_prefix = f"{prefix}{date_str}-{serie}"  # ex: 'bim2509-B'

            # On verrouille les lignes correspondantes pour éviter les collisions
            last_commande = (
                cls.objects
                .select_for_update(skip_locked=True)
                .filter(numero_facture__startswith=full_prefix)
                .order_by("-id")  # plus fiable que l'ordre lexicographique sur le code
                .first()
            )

            last_seq = 0
            if last_commande and last_commande.numero_facture:
                # extrait les chiffres terminaux (ex: 'bim2509-B001' -> '001')
                m = re.search(r'(\d+)$', last_commande.numero_facture)
                if m:
                    last_seq = int(m.group(1))  # ex: 1

            new_seq = last_seq + 1
            return f"{full_prefix}{str(new_seq).zfill(padding)}"  # ex: 'bim2509-B002'



class LigneCommande(AuditMixin):
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name="lignes_commandes")
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="lignes_commandes")
    prix_achat = models.PositiveIntegerField()
    prix_unitaire = models.PositiveIntegerField()
    quantite = models.PositiveIntegerField()
    # frais_livraison = models.PositiveIntegerField()

    def montant(self):
        return self.prix_unitaire * self.quantite
    
    def montant_achat(self):
        return self.prix_achat * self.quantite

    def marge(self):
        return self.montant() - self.montant_achat()

    # Renseigner automatiquement le prix_achat si l’appelant oublie de le donner
    def save(self, *args, **kwargs):
        if self.prix_achat is None:
            self.prix_achat = self.article.prix_achat
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.article.nom} x {self.quantite}"

class Vente(AuditMixin):
    commande = models.OneToOneField(Commande, on_delete=models.CASCADE, related_name='vente')
    date_encaissement = models.DateField(default=timezone.now)
    paiement = models.ForeignKey(Caisse, on_delete=models.PROTECT, related_name="paiement_ventes")
    montant = models.PositiveIntegerField()
    impot_synthetique = models.PositiveIntegerField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.montant:
            self.impot_synthetique = int(self.montant * 0.05)
        super().save(*args, **kwargs)

    @property
    def total(self):
        """Montant total TTC"""
        return (self.montant or 0) + (self.impot_synthetique or 0)

    def __str__(self):
        return f"Vente {self.commande.numero_facture} - Total : {self.total} Ar"
