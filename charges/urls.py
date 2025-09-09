from django.urls import path
from . import views

urlpatterns = [
    path("", views.charges_list, name="charges_list"),
    path('partial/', views.charges_list_partial, name='charges_list_partial'),
    path('ajouter/', views.ajouter_charge, name='ajouter_charge'),
    path("<int:pk>/modifier/", views.modifier_charge, name="modifier_charge"),
    path("<int:pk>/supprimer/", views.supprimer_charge, name="supprimer_charge"),
    path("<int:pk>/supprimer-definitivement/", views.supprimer_definitive_charge, name="supprimer_definitive_charge"),
    path("<int:pk>/restaurer/", views.restaurer_charge, name="restaurer_charge"),
]
