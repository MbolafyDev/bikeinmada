from django.core.management.base import BaseCommand
import pandas as pd
from livraison.models import Livraison

class Command(BaseCommand):
    help = "Importe les lieux depuis un fichier Excel"

    def add_arguments(self, parser):
        parser.add_argument("excel_file", type=str, help="Chemin vers le fichier Excel")

    def handle(self, *args, **kwargs):
        df = pd.read_excel(kwargs['excel_file'])
        df.columns = df.columns.str.strip().str.lower()  # nettoie les noms de colonnes

        for index, row in df.iterrows():
            try:
                lieu = str(row['lieu']).strip()
                categorie = str(row['categorie']).strip()
                frais = int(float(row['frais']))

                Livraison.objects.update_or_create(
                    lieu=lieu,
                    defaults={
                        'categorie': categorie,
                        'frais': frais
                    }
                )
            except Exception as e:
                self.stderr.write(f"Erreur à la ligne {index + 2} : {e}")

        self.stdout.write(self.style.SUCCESS("Importation des lieux terminée."))
