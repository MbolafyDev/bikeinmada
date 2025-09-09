from django.contrib import admin
from .models import Pages
# Register your models here.

@admin.register(Pages)
class PageAdmin(admin.ModelAdmin):
    list_display = ("nom", "contact")