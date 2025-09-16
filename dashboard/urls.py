from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="home"),
    # Endpoints HTMX (partials)
    path("cards/", views.dashboard_cards_partial, name="cards"),
    path("charts/", views.dashboard_charts_partial, name="charts"),
    path("tables/", views.dashboard_tables_partial, name="tables"),
]
