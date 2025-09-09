from django import forms
from .models import Inventaire

class InventaireForm(forms.ModelForm):
    class Meta:
        model = Inventaire
        fields = ['article', 'date', 'ajustement', 'remarque']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'ajustement': forms.NumberInput(attrs={'class': 'form-control'}),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'article': forms.Select(attrs={'class': 'form-select'}),
        }
