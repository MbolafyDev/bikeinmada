# users/forms.py
from django import forms
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm, PasswordResetForm, UserCreationForm
from django.core.exceptions import ValidationError
from .models import CustomUser

class ProfilForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'adresse', 'telephone', 'profil_photo']  # 🆕
        labels = {
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'adresse': 'Adresse',
            'telephone': 'Téléphone',
            'profil_photo': 'Photo de profil',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input w-full','placeholder': 'Votre prénom'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input w-full','placeholder': 'Votre nom'}),
            'adresse': forms.TextInput(attrs={'class': 'form-input w-full','placeholder': 'Votre adresse'}),
            'telephone': forms.TextInput(attrs={'class': 'form-input w-full','placeholder': 'Votre numéro de téléphone'}),
            'profil_photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),  # 🆕
        }

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control text-center','placeholder': 'Adresse e-mail'})
    )
    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cette adresse e-mail est déjà utilisée.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False
        if commit:
            user.save()
        return user

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class CustomPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "Aucun utilisateur avec cet email n'a été trouvé. "
                "Si vous n'avez pas encore de compte, vous pouvez en créer avec cette adresse email."
            )
        return email

# ✅ On conserve un PasswordChangeForm custom, basé sur celui de Django
class PasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['old_password', 'new_password1', 'new_password2']:
            self.fields[field_name].help_text = ""
        self.fields['old_password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Ancien mot de passe'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Nouveau mot de passe'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirmez le nouveau mot de passe'})
