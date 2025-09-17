from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_commandes, name='liste_commandes'),
    path('commandes/partial/', views.liste_commandes_partial, name='liste_commandes_partial'),
    path('commandes/creer/', views.creer_commande, name='commande_create'),  
    path("client-lookup/", views.client_lookup, name="client_lookup"),
    path('client-suggest/', views.client_suggest, name='client_suggest'),
    path('commandes/<int:commande_id>/', views.detail_commande, name='commande_detail'),  
    # path('commandes/<int:commande_id>/detail-modal/', views.commande_detail_ajax, name='commande_detail_modal'),
    path('commandes/<int:commande_id>/modifier/', views.commande_edit, name='commande_edit'),
    path('commandes/<int:commande_id>/supprimer/', views.commande_delete, name='commande_delete'),
    path('commandes/<int:commande_id>/restaurer/', views.commande_restore, name='commande_restore'),
    path('ventes/', views.journal_encaissement_ventes, name='liste_encaissement_ventes'),
    path('ventes/htmx/', views.journal_encaissement_ventes_partial, name='journal_encaissement_ventes_partial'),
    path('ventes/<int:pk>/modifier/', views.vente_encaissement_edit, name='vente_encaissement_edit'),
    path("ventes/encaisser/", views.encaissement_ventes, name="encaissement_ventes"),
    path("ventes/encaisser/traitement/", views.encaissement_ventes_groupes, name="valider_commandes_groupes"),
    path('ventes/<int:pk>/supprimer/', views.vente_encaissement_delete, name='vente_encaissement_delete'),
    path('statuts-ventes/', views.mise_a_jour_statuts_ventes, name='mise_a_jour_statuts_ventes'),
    path('statuts-ventes-groupes/', views.mise_a_jour_statuts_ventes_groupes, name='mise_a_jour_statuts_ventes_groupes'),
    path("facturation/", views.facturation_commandes, name="facturation"),
    path("facturation/partial/", views.facturation_commandes_partial, name="facturation_commandes_partial"),
    path('facturation/voir/', views.voir_factures, name='voir_factures'),
    path('facturation/imprimer/', views.imprimer_factures, name='imprimer_factures'),
    path('facturation/pdf/', views.factures_pdf, name='factures_pdf'),

]


