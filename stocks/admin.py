from django.contrib import admin
from .models import Inventaire

@admin.register(Inventaire)
class InvoentaireAdmin(admin.ModelAdmin):
    list_display = ('article', 'date')