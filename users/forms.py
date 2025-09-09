from django import forms
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, UserCreationForm
from django.core.exceptions import ValidationError
from .models import CustomUser

# forms.py
class ProfilForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'adresse', 'telephone']
        labels = {
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'adresse': 'Adresse',
            'telephone': 'Téléphone',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'placeholder': 'Votre prénom'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'placeholder': 'Votre nom'
            }),
            'adresse': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'placeholder': 'Votre adresse'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'placeholder': 'Votre numéro de téléphone'
            }),
        }

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control text-center',
            'placeholder': 'Adresse e-mail'
        })
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
        user.is_active = False  # Set inactive initially
        if commit:
            user.save()
        return user 

# Form for updating user information
class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class CustomPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()
        
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("Aucun utilisateur avec cet email n'a été trouvé. Si vous n'avez pas encore de compte, vous pouvez en créer avec cette adresse email.")
        
        return email

class PasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove help text for each password field
        for field_name in ['old_password', 'new_password1', 'new_password2']:
            self.fields[field_name].help_text = ""
        # Add custom styling or labels if needed
        self.fields['old_password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Ancien mot de passe'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Nouveau mot de passe'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirmez le nouveau mot de passe'})
