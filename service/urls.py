from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_commandes_services, name='liste_commandes_services'),
    path('commande/<int:commande_id>/', views.detail_commande_service, name='detail_commande_service'),
    path('commande/<int:commande_id>/detail-modal/', views.detail_commande_service_modal, name='detail_commande_service_modal'),
    path('commande/creer/', views.creer_commande_service, name='creer_commande_service'),
    path('commande/<int:commande_id>/modifier/', views.modifier_commande_service, name='modifier_commande_service'),
    path('commande/<int:commande_id>/supprimer/', views.supprimer_commande_service, name='supprimer_commande_service'),
    path('encaissements/', views.encaissement_services, name='encaissement_services'),
    path('encaissements/unitaire/', views.encaissement_service_unitaire, name='encaissement_service_unitaire'),
    path('facturation/', views.facturation_commandes_services, name='facturation_commandes_services'),
    path('facturation/partial/', views.facturation_commandes_services_partial, name='facturation_commandes_services_partial'),
    path('facturation/voir/', views.voir_factures_services, name='voir_factures_services'),
    path('facturation/imprimer/', views.imprimer_factures_services, name='imprimer_factures_services'),
    path("facturation/pdf/", views.telecharger_facture_service_pdf, name="telecharger_facture_service_pdf"),

]
