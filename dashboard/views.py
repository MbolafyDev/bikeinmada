from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, F, Value, BigIntegerField, ExpressionWrapper
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, Cast

from ventes.models import Commande, LigneCommande, Vente
from achats.models import Achat
from charges.models import Charge
from common.models import Pages, Caisse
# from common.decorators import admin_required  # si besoin

# -------------------- Constantes --------------------
BAD_SALE_STATUSES = ["Annulée", "Supprimée", "Reportée"]

# -------------------- Helpers --------------------
def _date_range_from_request(request):
    """
    period ∈ {jour | semaine | mois | annee | personnalise}
    date_from=YYYY-MM-DD, date_to=YYYY-MM-DD (si period=personnalise)
    """
    period = request.GET.get("period", "mois")
    tznow = timezone.localtime()
    today = tznow.date()

    if period == "jour":
        start, end = today, today

    elif period == "semaine":
        start = today - timedelta(days=today.weekday())  # lundi
        end = start + timedelta(days=6)

    elif period == "mois":
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)

    elif period == "annee":
        start = today.replace(month=1, day=1)
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)

    else:  # personnalisé
        try:
            start = timezone.datetime.fromisoformat(request.GET.get("date_from")).date()
            end = timezone.datetime.fromisoformat(request.GET.get("date_to")).date()
        except Exception:
            # fallback: mois courant
            start = today.replace(day=1)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)

    return start, end, period


def _optional_int(value):
    try:
        return int(value) if value not in (None, "", "0") else None
    except ValueError:
        return None

# -------------------- Core Query --------------------
def _query_dashboard_data(request):
    start, end, period = _date_range_from_request(request)
    page_id = _optional_int(request.GET.get("page"))
    caisse_id = _optional_int(request.GET.get("caisse"))

    # QuerySets via .actifs (hérités d'AuditMixin)
    ventes_qs = (
        Vente.actifs.select_related("commande", "paiement")
        .filter(date_encaissement__range=[start, end])
        .exclude(commande__statut_vente__in=BAD_SALE_STATUSES)
    )
    commandes_qs = (
        Commande.actifs.select_related("client", "page")
        .filter(date_commande__range=[start, end])
        .exclude(statut_vente__in=BAD_SALE_STATUSES)
    )
    lignes_qs = (
        LigneCommande.actifs.select_related("commande", "article")
        .filter(commande__date_commande__range=[start, end])
        .exclude(commande__statut_vente__in=BAD_SALE_STATUSES)
    )
    achats_qs = Achat.actifs.filter(date__range=[start, end])

    # ✅ Charges actives uniquement + comptes commençant par 6
    charges_qs = Charge.actifs.filter(
        date__range=[start, end],
        libelle__compte_numero__startswith="6",
    )

    # Filtres Page / Caisse
    if page_id:
        ventes_qs = ventes_qs.filter(commande__page_id=page_id)
        commandes_qs = commandes_qs.filter(page_id=page_id)
        lignes_qs = lignes_qs.filter(commande__page_id=page_id)
        charges_qs = charges_qs.filter(page_id=page_id)

    if caisse_id:
        ventes_qs = ventes_qs.filter(paiement_id=caisse_id)
        achats_qs = achats_qs.filter(paiement_id=caisse_id)
        charges_qs = charges_qs.filter(paiement_id=caisse_id)

    # KPI rapides
    tznow = timezone.localtime()
    today = tznow.date()
    ventes_today = (
        Vente.actifs.filter(date_encaissement=today)
        .exclude(commande__statut_vente__in=BAD_SALE_STATUSES)
    )
    if page_id:
        ventes_today = ventes_today.filter(commande__page_id=page_id)

    kpi = {
        "ca_periode": ventes_qs.aggregate(v=Coalesce(Sum("montant"), 0))["v"],
        "ca_jour": ventes_today.aggregate(v=Coalesce(Sum("montant"), 0))["v"],
        "nb_commandes": commandes_qs.count(),
        "nb_commandes_en_attente": commandes_qs.filter(statut_vente="En attente").count(),
        "achats_periode": achats_qs.aggregate(v=Coalesce(Sum("lignes_achats__montant"), 0))["v"],
        "charges_periode": charges_qs.aggregate(v=Coalesce(Sum("montant"), 0))["v"],
    }

    # Marge brute estimée (SIGNED pour MySQL)
    # marge = (prix_unitaire - prix_achat) * quantite
    marge_expr = ExpressionWrapper(
        (Cast(F("prix_unitaire"), BigIntegerField()) - Cast(F("prix_achat"), BigIntegerField()))
        * Cast(F("quantite"), BigIntegerField()),
        output_field=BigIntegerField(),
    )
    marge_brute = lignes_qs.aggregate(
        v=Coalesce(Sum(marge_expr, output_field=BigIntegerField()), Value(0), output_field=BigIntegerField())
    )["v"]

    # Encaissements par caisse (pie)
    encaissements_par_caisse = (
        ventes_qs.values("paiement__nom")
        .annotate(total=Coalesce(Sum("montant"), 0))
        .order_by("-total")
    )

    # Top articles
    top_articles = (
        lignes_qs.values("article__id", "article__nom")
        .annotate(
            qte=Coalesce(Sum("quantite"), 0),
            mnt=Coalesce(Sum(F("prix_unitaire") * F("quantite")), 0),
        )
        .order_by("-qte")[:5]
    )

    # Evolution CA : jour pour petites périodes, mois pour longues (mois/année/personnalisé large)
    if period in ("jour", "semaine"):
        evo = (
            ventes_qs.annotate(d=TruncDay("date_encaissement"))
            .values("d")
            .annotate(total=Coalesce(Sum("montant"), 0))
            .order_by("d")
        )
    elif period == "annee":
        evo = (
            ventes_qs.annotate(m=TruncMonth("date_encaissement"))
            .values("m")
            .annotate(total=Coalesce(Sum("montant"), 0))
            .order_by("m")
        )
    else:
        if (end - start).days <= 31:
            evo = (
                ventes_qs.annotate(d=TruncDay("date_encaissement"))
                .values("d")
                .annotate(total=Coalesce(Sum("montant"), 0))
                .order_by("d")
            )
        else:
            evo = (
                ventes_qs.annotate(m=TruncMonth("date_encaissement"))
                .values("m")
                .annotate(total=Coalesce(Sum("montant"), 0))
                .order_by("m")
            )

    # Commandes récentes & livraisons en cours
    commandes_recentes = commandes_qs.order_by("-created_at")[:5]
    livraisons_en_cours = (
        commandes_qs.exclude(statut_livraison__in=["Livrée", "Annulée", "Supprimée"])
        .order_by("-created_at")[:5]
    )

    ctx = {
        "start": start,
        "end": end,
        "period": period,
        "selected_page": page_id,
        "selected_caisse": caisse_id,
        "pages": Pages.actifs.all().order_by("nom"),
        "caisses": Caisse.actifs.all().order_by("nom"),

        "kpi": kpi,
        "marge_brute": marge_brute,
        "encaissements_par_caisse": list(encaissements_par_caisse),
        "top_articles": list(top_articles),
        "evolution": list(evo),

        "commandes_recentes": commandes_recentes,
        "livraisons_en_cours": livraisons_en_cours,
    }
    return ctx

# -------------------- Vues --------------------
@login_required
# @admin_required
def dashboard_home(request):
    ctx = _query_dashboard_data(request)
    return render(request, "dashboard/index.html", ctx)

@login_required
def dashboard_cards_partial(request):
    ctx = _query_dashboard_data(request)
    return render(request, "dashboard/partials/_cards.html", ctx)

@login_required
def dashboard_charts_partial(request):
    ctx = _query_dashboard_data(request)
    return render(request, "dashboard/partials/_charts.html", ctx)

@login_required
def dashboard_tables_partial(request):
    ctx = _query_dashboard_data(request)
    return render(request, "dashboard/partials/_tables.html", ctx)
