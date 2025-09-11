from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_livraisons, name='liste_livraisons'),
    path("partial/", views.liste_livraisons_partial, name="liste_livraisons_partial"),
    path('modifier-livraison/<int:commande_id>/', views.modifier_livraison, name='modifier_livraison'),
    # path('livreurs/', views.liste_livreurs, name='liste_livreurs'),
    # path('livreurs/ajouter/', views.ajouter_livreur, name='ajouter_livreur'),
    # path('livreurs/modifier/<int:id>/', views.modifier_livreur, name='modifier_livreur'),
    # path('livreurs/supprimer/<int:id>/', views.supprimer_livreur, name='supprimer_livreur'),
    path('commandes-a-livrer/', views.planification_livraison, name='planification_livraison'),
    path('assigner-livreur/', views.assigner_livreur_groupes, name='assigner_livreur_groupes'),
    path('fiche-livraison/', views.fiche_livraison, name='fiche_livraison'),
    path('fiche-de-suivi/', views.fiche_de_suivi, name='fiche_de_suivi'),
    # path('frais/', views.frais_livraison_list, name='frais_livraison_list'),
    # path('frais/ajouter/', views.frais_livraison_ajouter, name='frais_livraison_ajouter'),
    # path('frais/modifier/<int:id>/', views.frais_livraison_modifier, name='frais_livraison_modifier'),
    # path('frais/supprimer/<int:id>/', views.frais_livraison_supprimer, name='frais_livraison_supprimer'),
    path('paiement/', views.paiement_frais_livraisons, name='paiement_frais_livraisons'),
    path('paiement/traitement/', views.paiement_frais_livraisons_groupes, name='paiement_frais_livraisons_groupes'),
    path('paiement/modifier/<int:commande_id>/', views.modifier_frais_livraisons, name='modifier_frais_livraisons'),
    path('statuts/maj/', views.mise_a_jour_statuts_livraisons, name='mise_a_jour_statuts_livraisons'),
    path('statuts/maj/traitement/', views.mise_a_jour_statuts_livraisons_groupes, name='mise_a_jour_statuts_livraisons_groupes'),
]   
