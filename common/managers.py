# common/managers.py
from django.db import models

class ActifManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(statut_publication='supprimé')
