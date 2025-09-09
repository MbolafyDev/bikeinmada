from django.contrib import admin
from .models import Article

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('nom', 'reference', 'prix_achat', 'prix_vente', 'livraison', 'affiche_stock')

    def affiche_stock(self, obj):
        return obj.stock_actuel() 
    affiche_stock.short_description = "Stock actuel"