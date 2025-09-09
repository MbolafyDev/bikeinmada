from django.urls import path
from .views import compte_de_resultat, rapport_vente, bilan

urlpatterns = [
    path("compte-de-resultat/", compte_de_resultat, name="compte_de_resultat"),
    path('ventes/', rapport_vente, name='rapport_vente'),
    path('bilan/', bilan, name='bilan'),

]
