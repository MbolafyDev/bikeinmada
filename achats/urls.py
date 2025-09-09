from django.urls import path
from . import views

urlpatterns = [
    path('', views.achats_list, name='achats_list'),
    path('partial/', views.achats_list_partial, name='achats_list_partial'),
    path('ajouter/', views.achat_add, name='achat_add'),
    path('<int:pk>/', views.achat_detail, name='achat_detail'),
    path('<int:pk>/modal/', views.achat_detail_modal, name='achat_detail_modal'),
    path('<int:pk>/modifier/', views.achat_edit, name='achat_edit'),
    path('<int:pk>/supprimer/', views.achat_delete, name='achat_delete'),
    path('<int:pk>/supprimer-definitive/', views.achat_delete_definitive, name='achat_delete_defintive'),
    path("achat/<int:pk>/restaurer/", views.achat_restore, name="achat_restore"),
]
