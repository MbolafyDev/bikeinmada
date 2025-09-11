from django import forms
from .models import Livreur, Livraison

class LivreurForm(forms.ModelForm):
    class Meta:
        model = Livreur
        fields = ['nom', 'type', 'responsable', 'adresse', 'contact']

class LivraisonGroupForm(forms.Form):
    livreur = forms.ModelChoiceField(queryset=Livreur.objects.all(), label="Livreur")
    date_livraison = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Date de livraison")

class LivraisonForm(forms.ModelForm):
    class Meta:
        model = Livraison
        fields = ['lieu', 'categorie', 'frais_livraison', 'frais_livreur']
