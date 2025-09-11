from django.urls import path
from . import views

urlpatterns = [
    # Vue principale Configuration
    path('', views.configuration_view, name='configuration'),
    path("section/<str:section>/", views.configuration_section, name="configuration_section"),

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
]
