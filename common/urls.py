from django.urls import path
from . import views

urlpatterns = [
    path('', views.configuration_view, name='configuration'),
    
    path('ajouter_page/', views.ajouter_page, name='ajouter_page'),
    path('modifier_page/<int:pk>/', views.modifier_page, name='modifier_page'),
    path('supprimer_page/<int:pk>/', views.supprimer_page, name='supprimer_page'),

    path('ajouter_caisse/', views.ajouter_caisse, name='ajouter_caisse'),
    path('modifier_caisse/<int:pk>/', views.modifier_caisse, name='modifier_caisse'),
    path('supprimer_caisse/<int:pk>/', views.supprimer_caisse, name='supprimer_caisse'),

    path('ajouter_plan/', views.ajouter_plan, name='ajouter_plan'),
    path('modifier_plan/<int:pk>/', views.modifier_plan, name='modifier_plan'),
    path('supprimer_plan/<int:pk>/', views.supprimer_plan, name='supprimer_plan'),
]
