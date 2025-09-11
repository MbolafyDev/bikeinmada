from django.urls import path
from .import views

urlpatterns = [
    # path("compte-de-resultat/", compte_de_resultat, name="compte_de_resultat"),
    # path('ventes/', rapport_vente, name='rapport_vente'),
    # path('bilan/', bilan, name='bilan'),
    path("", views.statistiques_home, name="statistiques"),
    path("section/<str:section>/", views.statistiques_section, name="statistiques_section"),

]
