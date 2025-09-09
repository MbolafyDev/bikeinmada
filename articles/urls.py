from django.urls import path
from . import views
urlpatterns = [
    path('', views.article_list, name='article_list'),
    path("partial/", views.article_list_partial, name="article_list_partial"),
    path('creer/', views.article_create, name='article_create'),
    path('modifier/<int:pk>/', views.article_edit, name='article_edit'),
    path('supprimer/<int:pk>/', views.article_delete, name='article_delete'),
    path('supprimer-definitive/<int:pk>/', views.article_delete_definitive, name='article_delete_definitive'),
    path('restaurer/<int:pk>', views.article_restore, name='article_restore'),
    path('services/', views.service_list, name='service_list'),                     # Liste des services
    path('services/ajouter/', views.service_create, name='service_create'),         # Création
    path('services/modifier/<int:pk>/', views.service_edit, name='service_edit'),   # Édition
    path('services/supprimer/<int:pk>/', views.service_delete, name='service_delete'), # Suppression
]
