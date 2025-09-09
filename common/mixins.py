# common/models/mixins.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from common.managers import ActifManager

STATUT_PUBLICATION_CHOICES = [
    ('publié', 'Publié'),
    ('modifié', 'Modifié'),
    ('supprimé', 'Supprimé'),
]

class AuditMixin(models.Model):
    statut_publication = models.CharField(
        max_length=20,
        choices=STATUT_PUBLICATION_CHOICES,
        default='publié'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_created_%(class)s_set"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
       related_name="%(app_label)s_updated_%(class)s_set"
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_deleted_%(class)s_set"
    )
    created_at = models.DateTimeField(auto_now_add=True) # default=timezone.now
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()        # Le manager par défaut (tous les objets)
    actifs = ActifManager()           # Le manager filtré (sans les supprimés)
    
    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        self.statut_publication = 'supprimé'
        self.deleted_by = user
        self.save()
    
    def restore(self, user=None):
        """
        Annule un soft‑delete :
        - repasse le statut_publication à 'publié'
        - enlève la référence au deleted_by
        - met à jour updated_by (optionnel)
        """
        self.statut_publication = "publié"
        self.deleted_by = None
        if user is not None:
            self.updated_by = user
        # On met à jour seulement les champs modifiés
        self.save(update_fields=["statut_publication", "deleted_by", "updated_by", "updated_at"])
