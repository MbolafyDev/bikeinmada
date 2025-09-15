from django.db import migrations

# Ne PAS importer depuis models.py : recopier les constantes ici
FRAIS_LIVRAISON_PAR_DEFAUT = {
    'Ville': 3000,
    'Périphérie': 4000,
    'Super-périphérie': 5000,
    'Province': 3000,
}
FRAIS_LIVREUR_PAR_DEFAUT = {
    'Ville': 4000,
    'Périphérie': 5000,
    'Super-périphérie': 6000,
    'Province': 4000,
}

def apply_defaults(apps, schema_editor):
    Livraison = apps.get_model('livraison', 'Livraison')
    from django.db.models import Q

    # Met à jour frais_livreur là où il est NULL ou 0
    for cat, val in FRAIS_LIVREUR_PAR_DEFAUT.items():
        Livraison.objects.filter(
            Q(frais_livreur__isnull=True) | Q(frais_livreur=0),
            categorie=cat
        ).update(frais_livreur=val)

    # Met à jour frais_livraison là où il est NULL ou 0
    for cat, val in FRAIS_LIVRAISON_PAR_DEFAUT.items():
        Livraison.objects.filter(
            Q(frais_livraison__isnull=True) | Q(frais_livraison=0),
            categorie=cat
        ).update(frais_livraison=val)

class Migration(migrations.Migration):

    dependencies = [
        ('livraison', '0008_rename_frais_livraison_frais_livraison_and_more'),  # dernière migration
    ]

    operations = [
        migrations.RunPython(apply_defaults, reverse_code=migrations.RunPython.noop),
    ]
