from django.urls import path
from .views import CustomPasswordResetView, CustomLoginView
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),

    path("creation/", views.SignUpView.as_view(), name="signup"),
    path("creation/confirmation/<int:uid>/<str:token>/", views.ConfirmEmailView.as_view(), name="confirm_email"),
    path("creation/confirmation/check-email/", TemplateView.as_view(template_name='users/compte_creation_email_confirmation.html'), name="check_email"),
    path("creation/confirmation/resend/", views.ResendConfirmationView.as_view(), name="resend_confirmation"),
    path("creation/success/", TemplateView.as_view(template_name="users/compte_creation_success.html"), name="creation_success"),

    path("reinitialisation/", CustomPasswordResetView.as_view(), name="password_reset"),
    path("reinitialisation/email/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reinitialisation/confirmation/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reinitialisation/complete/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    path('profil/', views.profil_view, name='profil'),
    path('profil/modifier/', views.modifier_profil, name='modifier_profil'),

]
