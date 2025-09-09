from django.urls import path
from . import views

urlpatterns = [
    path('', views.etat_caisses, name='etat_caisses'),
    path("mouvements/", views.mouvements_list, name="mouvements_list"),
    path("mouvement/ajouter/", views.ajouter_mouvement, name="ajouter_mouvement"),
    path('mouvements/modifier/<int:mouvement_id>/', views.modifier_mouvement, name='modifier_mouvement'),
    path("mouvement/<int:mouvement_id>/supprimer/", views.supprimer_mouvement, name="supprimer_mouvement"),
    path("versements/", views.versements_list, name="versements_list"),
    path("versements/ajouter/", views.ajouter_versement, name="ajouter_versement"),
    path("versement/modifier/<int:pk>/", views.modifier_versement, name="modifier_versement"),
    path("versement/supprimer/<int:pk>/", views.supprimer_versement, name="supprimer_versement"),
]
