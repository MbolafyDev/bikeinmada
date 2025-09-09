from django.urls import path
from . import views

urlpatterns = [
    path("", views.clients_list, name="clients_list"),
    path("partial/", views.clients_list_partial, name="clients_list_partial"),
    path("ajouter/", views.client_create, name="client_create"),
    path("<int:client_id>/modifier/", views.client_update, name="client_update"),
    path("<int:client_id>/supprimer/", views.client_delete, name="client_delete"),
    path("entreprises/", views.entreprises_list, name="entreprises_list"),
    path("entreprise/create/", views.entreprise_create, name="entreprise_create"),
    path("entreprise/<int:entreprise_id>/update/", views.entreprise_update, name="entreprise_update"),
    path("entreprise/<int:entreprise_id>/delete/", views.entreprise_delete, name="entreprise_delete"),

]
