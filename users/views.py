from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView, PasswordChangeView
from django.contrib.auth.tokens import default_token_generator
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator 
from django.urls import reverse, reverse_lazy
from django.views.generic import View, CreateView, TemplateView
from .forms import CustomUserCreationForm, PasswordChangeForm, CustomPasswordResetForm, ProfilForm

User = get_user_model()

# Utility function to send email confirmation
def send_confirmation_email(user, request):
    token = default_token_generator.make_token(user)
    uid = user.pk
    confirm_url = request.build_absolute_uri(
        reverse('confirm_email', kwargs={'uid': uid, 'token': token})
    )
    subject = "Confirmez votre email"
    message = f"Cliquez sur le lien suivant pour confirmer la création de votre compte : {confirm_url}"
    user.email_user(subject, message)

class CustomLoginView(LoginView):
    template_name = "users/compte_login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if not user.is_active:
            send_confirmation_email(user, self.request)
            return redirect(reverse('check_email')) # Redirect to the "check_email" page

        if not user.is_validated_by_admin:
            messages.error(self.request, "Votre compte est en attente de validation par un administrateur.")
            return redirect('login')  
        
        # Proceed with login for active users
        login(self.request, user)
        return super().form_valid(form)

    def form_invalid(self, form):
        # Check if the user exists but is inactive
        username = self.request.POST.get('username')
        user = User.objects.filter(username=username).first()
        if user and not user.is_active:
            # Handle inactive user
            send_confirmation_email(user, self.request)
            messages.error(self.request, "Votre compte n'est pas encore activé. Un nouveau lien vous a été envoyé.")
            return redirect(reverse('check_email'))  # Redirect to the "check_email" page
        # Handle other invalid credentials
        return super().form_invalid(form)

# User Registration View
class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("check_email")
    template_name = "users/compte_creation.html"

    def form_valid(self, form):
        user = form.save()
        user.is_active = False  # Ensure new users are inactive until email confirmation
        user.save()
        send_confirmation_email(user, self.request)
        return render(self.request, "users/compte_creation_email_confirmation.html", context={"user": user})

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('/')
        return super().dispatch(request, *args, **kwargs)

# Email Confirmation View
class ConfirmEmailView(View):
    def get(self, request, uid, token):
        user = get_object_or_404(User, pk=uid)
        if default_token_generator.check_token(user, token):
            user.is_active = False  # Toujours inactif tant que l’admin n’a pas validé
            user.save()
            messages.success(request, "Votre email a été confirmé. Votre compte sera activé après validation par un administrateur.")
            return redirect('login')
        else:
            return render(request, 'users/compte_creation_invalid_token.html', context={"user": user})

# Resend Confirmation Email View
@method_decorator(login_required, name='dispatch')  # Ensure user is logged in
class ResendConfirmationView(View):
    def get(self, request):
        user = request.user
        if not user.is_active:  # Check if the user is inactive
            send_confirmation_email(user, request)  # Send confirmation email
            messages.success(
                request,
                "Un nouveau lien de confirmation a été envoyé à votre addresse email."
            )
            return redirect('check_email')  # Redirect to the "check_email" page
        # If the user is already active, redirect them to the home page
        messages.info(request, "Votre compte est déjà active.")
        return redirect('login')

class LogoutView(LogoutView):
    next_page = reverse_lazy("login")  # Redirect to login after logout.

class AccountCreationSuccessView(TemplateView):
    template_name = 'users/compte_creation_success.html'

class CustomPasswordResetView(PasswordResetView):
    template_name = "users/compte_reinitialisation_mdp.html"
    form_class = CustomPasswordResetForm
    success_url = reverse_lazy("password_reset_done")

class PasswordResetDoneView(PasswordResetDoneView):
    template_name = "users/compte_reinitialisation_mdp_link_sent.html"

class PasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "users/compte_reinitialisation_mdp_confirmation.html"
    success_url = reverse_lazy("password_reset_complete")

class PasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "users/compte_reinitialisation_mdp_complete.html"

class UserPasswordUpdateView(SuccessMessageMixin, PasswordChangeView):
    form_class = PasswordChangeForm
    template_name = 'users/maj_securite.html'
    success_url = reverse_lazy('maj_mdp_success')  
    success_message = "Votre mot de passe a été mis à jour avec succès!"

    def form_valid(self, form):
        # Save the new password
        response = super().form_valid(form)
        # Log out the user after password change
        logout(self.request)
        return response

@login_required
def profil_view(request):
    user = request.user
    form = ProfilForm(request.POST or None, instance=user)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('profil')

    return render(request, 'users/profil.html', {
        'user': user,
        'form': form,
    })

@login_required
def modifier_profil(request):
    user = request.user

    if request.method == 'POST':
        form = ProfilForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('profil')  # Remplace 'profil' par l’URL de la page d’accueil ou de confirmation
    else:
        form = ProfilForm(instance=user)

    return render(request, 'users/modifier_profil.html', {
        'form': form,
    })