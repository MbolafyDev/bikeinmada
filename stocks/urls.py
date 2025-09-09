from django.urls import path
from . import views

urlpatterns = [
    path('', views.etat_stock, name='etat_stock'),
    path("partial/", views.etat_stock_partial, name="etat_stock_partial"),
    path('ajuster-inventaire/', views.ajuster_inventaire, name='ajuster_inventaire'),
    path('inventaires/', views.inventaire_list, name='inventaire_list'),
    path('inventaires/<int:pk>/modifier/', views.inventaire_edit, name='inventaire_edit'),
    path('inventaires/<int:pk>/supprimer/', views.inventaire_delete, name='inventaire_delete'),
    path('inventaires/<int:pk>/supprimer-definitive/', views.inventaire_delete_definitive, name='inventaire_delete_definitive'),
    path('inventaires/<int:pk>/restaurer/', views.inventaire_restore, name='inventaire_restore'),
]
