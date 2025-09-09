from django.db import models
from articles.models import Article
from common.mixins import AuditMixin

class Inventaire(AuditMixin):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="inventaires")
    date = models.DateField("Date d'inventaire")
    ajustement = models.IntegerField("Ajustement quantité", default=0)
    remarque = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Inventaire de {self.article.nom} le {self.date} : {self.ajustement}"

