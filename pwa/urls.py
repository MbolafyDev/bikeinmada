from django.urls import path
from .views import ManifestView, service_worker, offline

urlpatterns = [
    path("manifest.webmanifest", ManifestView.as_view(), name="manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("offline/", offline, name="offline"),  # page de secours hors-ligne
]
