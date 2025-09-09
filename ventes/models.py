from django.db import models, transaction, IntegrityError
from django.utils import timezone
import time

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

    livreur = models.ForeignKey(Livreur, null=True, blank=True, on_delete=models.SET_NULL)
    frais_livreur = models.PositiveIntegerField(null=True, blank=True,default=0)
    paiement_frais_livreur = models.CharField(
        max_length=15,
        choices=FRAIS_LIVREUR_CHOIX,
        default='Non payée'
    )

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
            or self.statut_publication == "supprimé"
        )
    
    @classmethod
    def generer_numero_facture_atomic(cls):
        with transaction.atomic():
            prefix = "F"
            date_str = timezone.now().strftime("%y%m%d")

            last_commande = (
                cls.objects
                .select_for_update()
                .filter(numero_facture__startswith=f"{prefix}{date_str}")
                .order_by('-numero_facture')
                .first()
            )

            if last_commande:
                last_number = int(last_commande.numero_facture.split("-")[-1])
            else:
                last_number = 0

            new_number = last_number + 1
            return f"{prefix}{date_str}-{new_number:03d}"


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
    paiement = models.ForeignKey(Caisse, on_delete=models.PROTECT, related_name="ventes_ventes")
    montant = models.PositiveIntegerField() 

    def __str__(self):
        return f"Vente de la commande {self.commande.numero_facture} - {self.montant} Ar"
