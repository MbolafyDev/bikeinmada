from django import forms
from .models import Article, Service

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['nom', 'image', 'reference', 'prix_achat', 'prix_vente', 'livraison']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),  # 👈 Ajout
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'prix_achat': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_vente': forms.NumberInput(attrs={'class': 'form-control'}),
            'livraison': forms.Select(attrs={'class': 'form-select'}),
        }

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['nom', 'reference', 'tarif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'tarif': forms.NumberInput(attrs={'class': 'form-control'}),
        }