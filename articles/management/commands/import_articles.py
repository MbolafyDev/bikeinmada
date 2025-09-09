from django.core.management.base import BaseCommand
import pandas as pd
from articles.models import Article  

class Command(BaseCommand):
    help = 'Importe les articles depuis un fichier Excel'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Chemin vers le fichier Excel')

    def handle(self, *args, **kwargs):
        df = pd.read_excel(kwargs['excel_file'])
        df.columns = df.columns.str.strip().str.lower()  # Nettoie les noms de colonnes

        for _, row in df.iterrows():
            try:
                Article.objects.update_or_create(
                    reference=str(row['reference']).strip(),
                    defaults={
                        'nom': str(row['nom']).strip(),
                        'prix_achat': int(float(row["prix_achat"])),
                        'prix_vente': int(float(row["prix_vente"])),
                        'livraison': str(row['livraison']).strip().capitalize(),
                    }
                )
            except Exception as e:
                self.stderr.write(f"Erreur ligne {_ + 2} : {e}")
        
        self.stdout.write(self.style.SUCCESS("Importation terminée."))
