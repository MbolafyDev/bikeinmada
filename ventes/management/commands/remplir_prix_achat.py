# ventes/management/commands/remplir_prix_achat.py

from django.core.management.base import BaseCommand
from ventes.models import LigneCommande

class Command(BaseCommand):
    help = "Remplit le champ prix_achat des lignes de commande à partir du prix d'achat de l'article"

    def handle(self, *args, **kwargs):
        lignes = LigneCommande.objects.filter(prix_achat__isnull=True).select_related('article')
        total = lignes.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Aucune ligne à mettre à jour."))
            return

        updated = 0
        for ligne in lignes:
            if ligne.article and ligne.article.prix_achat is not None:
                ligne.prix_achat = ligne.article.prix_achat
                ligne.save(update_fields=['prix_achat'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"{updated} lignes mises à jour sur {total}."))