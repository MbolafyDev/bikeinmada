from django import template

register = template.Library()

@register.filter
def couleur_page(nom_page):
    couleurs_pages = {
        "Zara Store": "rgb(200, 220, 255)",       # Bleu clair
        "Solde By Hanï": "rgb(255, 200, 200)",    # Rose clair
        "Caprice Home": "rgb(255, 204, 153)",     # Abricot
        "Cozy Home": "rgb(255, 229, 180)",        # Orange pêche
    }
    return couleurs_pages.get(nom_page, "white")
