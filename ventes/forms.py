from django import forms
from .models import Vente

class VenteForm(forms.ModelForm):
    class Meta:
        model = Vente
        fields = ['paiement', 'montant']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paiement'].widget.attrs.update({'class': 'form-select'})
        self.fields['montant'].widget.attrs.update({
            'class': 'form-control',
            'readonly': 'readonly'
        })