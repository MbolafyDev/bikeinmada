from django.urls import path
from . import views

from .views import (
    configuration_view, configuration_section,
    config_user_update,
    # ... les autres actions
)

urlpatterns = [
    # Vue principale Configuration
    path('', views.configuration_view, name='configuration'),
    path("section/<str:section>/", configuration_section, name="configuration_section"),
    path("config/utilisateur/<int:user_id>/update/", views.config_user_update, name="config_user_update"),
    path("config/utilisateur/<int:user_id>/delete/", views.config_user_delete, name="config_user_delete"),

    # Profil (dans Configuration)
    path("profil/update/", views.configuration_profil_update, name="configuration_profil_update"),

    # Pages
    path('ajouter_page/', views.ajouter_page, name='ajouter_page'),
    path('modifier_page/<int:pk>/', views.modifier_page, name='modifier_page'),
    path('supprimer_page/<int:pk>/', views.supprimer_page, name='supprimer_page'),

    # Caisses
    path('ajouter_caisse/', views.ajouter_caisse, name='ajouter_caisse'),
    path('modifier_caisse/<int:pk>/', views.modifier_caisse, name='modifier_caisse'),
    path('supprimer_caisse/<int:pk>/', views.supprimer_caisse, name='supprimer_caisse'),

    # Plan des comptes
    path('ajouter_plan/', views.ajouter_plan, name='ajouter_plan'),
    path('modifier_plan/<int:pk>/', views.modifier_plan, name='modifier_plan'),
    path('supprimer_plan/<int:pk>/', views.supprimer_plan, name='supprimer_plan'),

    # Livreurs
    path('ajouter_livreur/', views.ajouter_livreur, name='ajouter_livreur'),
    path('modifier_livreur/<int:id>/', views.modifier_livreur, name='modifier_livreur'),
    path('supprimer_livreur/<int:id>/', views.supprimer_livreur, name='supprimer_livreur'),

    # Frais de livraison
    path('frais/ajouter/', views.frais_livraison_ajouter, name='frais_livraison_ajouter'),
    path('frais/modifier/<int:id>/', views.frais_livraison_modifier, name='frais_livraison_modifier'),
    path('frais/supprimer/<int:id>/', views.frais_livraison_supprimer, name='frais_livraison_supprimer'),

    path('articles/ajouter-categorie/', views.ajouter_categorie, name="ajouter_categorie"),
    path('articles/<int:pk>/modifier-categorie/', views.modifier_categorie, name="modifier_categorie"),
    path('articles/<int:pk>/supprimer-categorie/', views.supprimer_categorie, name="supprimer_categorie"),

    path('articles/ajouter-taille/', views.ajouter_taille, name="ajouter_taille"),
    path('articles/<int:pk>/modifier-taille/', views.modifier_taille, name="modifier_taille"),
    path('articles/<int:pk>/supprimer-taille/', views.supprimer_taille, name="supprimer_taille"),

    path('articles/ajouter-couleur/', views.ajouter_couleur, name="ajouter_couleur"),
    path('articles/<int:pk>/modifier-couleur/', views.modifier_couleur, name="modifier_couleur"),
    path('articles/<int:pk>/supprimer-couleur/', views.supprimer_couleur, name="supprimer_couleur"),

    path("roles/ajouter/", views.ajouter_role, name="ajouter_role"),
    path("roles/<int:pk>/modifier/", views.modifier_role, name="modifier_role"),
    path("roles/<int:pk>/supprimer/", views.supprimer_role, name="supprimer_role"),
]
