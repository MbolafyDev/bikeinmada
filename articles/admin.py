# articles/admin.py
from django.contrib import admin
from .models import Article, Service, Categorie, Taille, Couleur

# ---- Référentiels ----
@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("categorie",)
    search_fields = ("categorie",)
    ordering = ("categorie",)

@admin.register(Taille)
class TailleAdmin(admin.ModelAdmin):
    list_display = ("taille",)
    search_fields = ("taille",)
    ordering = ("taille",)

@admin.register(Couleur)
class CouleurAdmin(admin.ModelAdmin):
    list_display = ("couleur",)
    search_fields = ("couleur",)
    ordering = ("couleur",)

# ---- Articles & Services ----
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "nom", "reference", "prix_achat", "prix_vente", "livraison",
        "categorie", "taille", "couleur"
    )
    list_filter = ("livraison", "categorie", "taille", "couleur")
    search_fields = ("nom", "reference")
    autocomplete_fields = ("categorie", "taille", "couleur")
    # Si tu préfères des menus déroulants simples, supprime la ligne ci-dessus.

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("nom", "reference", "tarif")
    search_fields = ("nom", "reference")
