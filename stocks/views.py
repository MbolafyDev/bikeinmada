# stocks/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.http import QueryDict
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate
from django.contrib import messages
from django.db.models import Sum
from datetime import date

from common.decorators import admin_required
from common.utils import is_admin, resolve_display_mode  
from .models import Inventaire
from articles.models import Article
from achats.models import LigneAchat
from ventes.models import LigneCommande
from .forms import InventaireForm 

def build_etat_stock_context(request):
    query = request.GET.get("q", "").strip()
    filtre_article = request.GET.get("filtre_article", "").strip()
    filtre_entree = request.GET.get("filtre_entree")
    filtre_sortie = request.GET.get("filtre_sortie")
    filtre_stock = request.GET.get("filtre_stock")

    # Articles filtrés par nom
    filtered_articles = Article.actifs.all()
    if query:
        filtered_articles = filtered_articles.filter(nom__icontains=query)
    filtered_articles = filtered_articles.order_by("nom")

    # Pré-calculs
    achats_valides = LigneAchat.objects.filter(
        achat__statut_publication__iexact="publié"
    ).values("article_id").annotate(total_entrees=Sum("quantite"))

    commandes_valides = LigneCommande.objects.filter(
        commande__statut_publication__iexact="publié"
    ).exclude(
        commande__statut_vente__in=["Supprimée", "Annulée", "Reportée"]
    ).values("article_id").annotate(total_sorties=Sum("quantite"))

    inventaires_valides = Inventaire.objects.filter(
        statut_publication__iexact="publié"
    ).values("article_id").annotate(total_ajustements=Sum("ajustement"))

    entrees_map = {e["article_id"]: e["total_entrees"] or 0 for e in achats_valides}
    sorties_map = {s["article_id"]: s["total_sorties"] or 0 for s in commandes_valides}
    ajustements_map = {a["article_id"]: a["total_ajustements"] or 0 for a in inventaires_valides}

    data = []
    total_valeur = 0

    for article in filtered_articles:
        entrees = entrees_map.get(article.id, 0)
        sorties = sorties_map.get(article.id, 0)
        ajustements = ajustements_map.get(article.id, 0)
        stock_final = entrees - sorties + ajustements
        valeur = stock_final * article.prix_achat if stock_final > 0 else 0

        # Filtres secondaires
        if filtre_article and filtre_article.lower() not in article.nom.lower():
            continue
        if filtre_entree and entrees < int(filtre_entree):
            continue
        if filtre_sortie and sorties < int(filtre_sortie):
            continue
        if filtre_stock and stock_final < int(filtre_stock):
            continue

        data.append({
            "article": article,
            "entrees": entrees,
            "sorties": sorties,
            "ajustements": ajustements,
            "stock_final": stock_final,
            "pu": article.prix_achat,
            "valeur": valeur
        })

        if stock_final > 0:
            total_valeur += valeur

    # Pagination
    paginator = Paginator(data, 24)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    data_page = page_obj.object_list

    # QS propre (sans page)
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != "page":
            clean_params.setlist(key, clean_values)
    extra_querystring = "&" + clean_params.urlencode() if clean_params else ""

    display_mode = resolve_display_mode(request, session_key="display_etat_stock", default="cards")

    return {
        "data": data_page,
        "total_valeur": total_valeur,
        "form": InventaireForm(),
        "query": query,
        "today": date.today().isoformat(),
        "is_admin": is_admin(request.user),
        "page_obj": page_obj,
        "extra_querystring": extra_querystring,
        "display_mode": display_mode,  # 👈 important
    }

@login_required
def etat_stock(request):
    ctx = build_etat_stock_context(request)
    return render(request, "stocks/etat_stock.html", ctx)

@login_required
def etat_stock_partial(request):
    ctx = build_etat_stock_context(request)
    # Si pas HTMX -> renvoyer la page complète (utile en accès direct)
    if request.headers.get("HX-Request") != "true":
        return render(request, "stocks/etat_stock.html", ctx)
    # HTMX -> seulement le wrapper
    return render(request, "stocks/includes/etat_stock_list_wrapper.html", ctx)

@login_required
@admin_required
def inventaire_list(request):
    query = request.GET.get("q", "").strip()
    
    inventaires = Inventaire.objects.select_related('article').order_by('-date')
    
    if query:
        inventaires = inventaires.filter(article__nom__icontains=query)

    if request.method == "POST":
        form = InventaireForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("etat_stock")  # ou autre URL
    else:
        form = InventaireForm()
    
    return render(request, 'stocks/inventaire_list.html', {
        'inventaires': inventaires,
        'form': form,
        'query': query,  
        'today': date.today().isoformat(),
        "is_admin": is_admin(request.user),
    })

def ajuster_inventaire(request):
    if request.method == "POST":
        form = InventaireForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("etat_stock")  
    else:
        return redirect("inventaire_list") 

@login_required
@admin_required
@require_POST
def inventaire_edit(request, pk):
    inventaire = get_object_or_404(Inventaire, pk=pk)
    inventaire.date = request.POST.get("date")
    inventaire.ajustement = request.POST.get("ajustement")
    inventaire.remarque = request.POST.get("remarque")
    inventaire.save()
    return redirect('inventaire_list')

@login_required
@admin_required
@require_POST
def inventaire_delete(request, pk):
    inventaire = get_object_or_404(Inventaire, pk=pk)
    inventaire.soft_delete(user=request.user)
    return redirect('inventaire_list')

@login_required
@admin_required
@require_POST
def inventaire_delete_definitive(request, pk):
    inventaire = get_object_or_404(Inventaire, pk=pk)
    password = request.POST.get('password')
    user = authenticate(username=request.user.username, password=password)

    if user is not None:
        inventaire.delete()
        messages.success(request, f"L’inventaire du {inventaire.date} a été supprimé définitivement.")
    else:
        messages.warning(request, "Mot de passe incorrect. Suppression annulée.")

    return redirect('inventaire_list')

@login_required
@admin_required
@require_POST
def inventaire_restore(request, pk):
    inventaire = get_object_or_404(Inventaire, pk=pk)
    password = request.POST.get('password')
    user = authenticate(username=request.user.username, password=password)

    if user is not None:
        inventaire.restore(user=request.user)
        messages.success(request, f"L’inventaire du {inventaire.date} a été restauré avec succès.")
    else:
        messages.warning(request, "Mot de passe incorrect. Restauration annulée.")

    return redirect('inventaire_list')
