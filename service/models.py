from django.db import models, transaction, IntegrityError
from django.utils import timezone
import time

from clients.models import Entreprise
from articles.models import Service
from common.models import Pages, Caisse
from common.constants import ETAT_CHOIX
from common.mixins import AuditMixin  


class Commande(AuditMixin):   
    numero_proforma = models.CharField(max_length=20, unique=True, editable=False)
    date_commande = models.DateField(default=timezone.now)
    client = models.ForeignKey(Entreprise, on_delete=models.CASCADE)
    page = models.ForeignKey(Pages, null=True, default=1, on_delete=models.SET_NULL, related_name="service_commandes")
    remarque = models.TextField(blank=True, null=True)
    
    statut_vente = models.CharField(max_length=20, choices=ETAT_CHOIX, default='En attente')
    
    def __str__(self):
        return f"Proforma {self.numero_proforma} - {self.client.raison_sociale}"
    
    @property
    def montant_commande(self):
        return sum(ligne.montant() for ligne in self.lignes_commandes.all()) 
 
    def save(self, *args, **kwargs):
        max_attempts = 5
        for attempt in range(max_attempts):
            if not self.numero_proforma:
                self.numero_proforma = self.__class__.generer_numero_proforma_atomic()
            try:
                super().save(*args, **kwargs)
                break  # Success
            except IntegrityError as e:
                if "Duplicate entry" in str(e):
                    time.sleep(0.1)  # backoff léger
                    self.numero_proforma = None  # forcer la régénération
                    continue
                raise
        else:
            raise IntegrityError("Impossible de générer un numero_proforma unique après plusieurs tentatives")

    # Désactiver la modification selon les statuts 
    def actions_desactivees(self):
        return (
            self.statut_vente in ["Payée", "Annulée", "Supprimée"]
            or self.statut_publication == "supprimé"
        )
    
    @classmethod
    def generer_numero_proforma_atomic(cls):
        with transaction.atomic():
            prefix = "P"
            date_str = timezone.now().strftime("%y%m%d")

            last_commande = (
                cls.objects
                .select_for_update()
                .filter(numero_proforma__startswith=f"{prefix}{date_str}")
                .order_by('-numero_proforma')
                .first()
            )

            if last_commande:
                last_number = int(last_commande.numero_proforma.split("-")[-1])
            else:
                last_number = 0

            new_number = last_number + 1
            return f"{prefix}{date_str}-{new_number:03d}"


class LigneCommande(AuditMixin):
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name="lignes_commandes")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="lignes_commandes")
    tarif = models.PositiveIntegerField()
    quantite = models.PositiveIntegerField()

    def montant(self):
        return self.tarif * self.quantite

    def __str__(self):
        return f"{self.service.nom} x {self.quantite}"


class Vente(AuditMixin):
    commande = models.OneToOneField(Commande, on_delete=models.CASCADE, related_name='vente')
    numero_facture = models.CharField(max_length=20, unique=True, editable=False, null=True, blank=True,)
    date_encaissement = models.DateField(default=timezone.now)
    paiement = models.ForeignKey(Caisse, on_delete=models.PROTECT, related_name="service_ventes")
    reference = models.CharField(max_length=50, blank=True, null=True)
    montant = models.PositiveIntegerField()

    def __str__(self):
        return f"Facture {self.numero_facture} - {self.montant} Ar"

    def save(self, *args, **kwargs):
        max_attempts = 5
        for attempt in range(max_attempts):
            if not self.numero_facture:
                self.numero_facture = self.__class__.generer_numero_facture_atomic()
            try:
                super().save(*args, **kwargs)
                break
            except IntegrityError as e:
                if "Duplicate entry" in str(e):
                    time.sleep(0.1)
                    self.numero_facture = None
                    continue
                raise
        else:
            raise IntegrityError("Impossible de générer un numero_facture unique après plusieurs tentatives")

    @classmethod
    def generer_numero_facture_atomic(cls):
        with transaction.atomic():
            prefix = "F"
            date_str = timezone.now().strftime("%y%m%d")

            last_vente = (
                cls.objects
                .select_for_update()
                .filter(numero_facture__startswith=f"{prefix}{date_str}")
                .order_by('-numero_facture')
                .first()
            )

            if last_vente:
                last_number = int(last_vente.numero_facture.split("-")[-1])
            else:
                last_number = 0

            new_number = last_number + 1
            return f"{prefix}{date_str}-{new_number:03d}"
