from django import forms
from .models import Article, Service, Taille, Couleur, Categorie

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            'nom', 'image', 'reference', 'prix_achat', 'prix_vente',
            'livraison', 'taille', 'couleur', 'categorie'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'prix_achat': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_vente': forms.NumberInput(attrs={'class': 'form-control'}),
            'livraison': forms.Select(attrs={'class': 'form-select'}),
            'taille': forms.Select(attrs={'class': 'form-select'}),
            'couleur': forms.Select(attrs={'class': 'form-select'}),
            'categorie': forms.Select(attrs={'class': 'form-select'}),
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
