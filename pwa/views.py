# pwa/views.py
from django.conf import settings
from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import HttpResponse


class ManifestView(TemplateView):
    template_name = "pwa/manifest.webmanifest"
    content_type = "application/manifest+json"


def service_worker(request):
    """
    Sert le Service Worker depuis /service-worker.js
    - Pas de cache côté client pour permettre les mises à jour
    - Scope autorisé à la racine du site
    """
    response = render(
        request,
        "pwa/service-worker.js",
        {"APP_VERSION": getattr(settings, "APP_VERSION", "0")},
        content_type="application/javascript",
    )
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    """Page de secours lorsque l’utilisateur est hors-ligne."""
    return render(request, "pwa/offline.html", status=200)
