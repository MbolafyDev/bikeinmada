"""
URL configuration for zarastore project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from pwa import views as pwa_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('ventes.urls')),
    path('users/', include('users.urls')),
    path('articles/', include('articles.urls')),
    path('achats/', include('achats.urls')),
    path('stocks/', include('stocks.urls')),
    path('clients/', include('clients.urls')),
    path('configuration/', include('common.urls')),
    path('charges/', include('charges.urls')),
    path('caisses/', include('caisses.urls')),
    path('livraison/', include('livraison.urls')),
    path('statistiques/', include('statistiques.urls')),
    path('services/', include('service.urls')),
    path('configuration/', include('configuration.urls')),

    # Routes PWA à la racine du domaine
    path("manifest.webmanifest", pwa_views.ManifestView.as_view(), name="manifest"),
    path("service-worker.js", pwa_views.service_worker, name="service_worker"),
    path("offline/", pwa_views.offline, name="offline"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

