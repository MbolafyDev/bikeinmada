# achats/views.py 
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse, QueryDict
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate
from django.contrib import messages 
from datetime import date
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from common.decorators import admin_required
from .models import Achat, LigneAchat
from common.models import Caisse
from common.utils import is_admin, resolve_display_mode
from articles.models import Article
from .forms import AchatForm
import json

def build_achats_context(request):
    achats = Achat.objects.select_related('paiement') \
                          .prefetch_related('lignes_achats__article') \
                          .order_by('-date')

    # Filtres
    article_id   = request.GET.get('article')
    date_filter  = request.GET.get('date_filter')
    paiement_id  = request.GET.get('paiement')

    if article_id:
        achats = achats.filter(lignes_achats__article_id=article_id).distinct()

    if date_filter:
        d = parse_date(date_filter)
        if d:
            achats = achats.filter(date=d)

    if paiement_id:
        achats = achats.filter(paiement_id=paiement_id)

    # Pagination
    paginator   = Paginator(achats, 18)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    # QS propre (préserver filtres, enlever 'page' vide)
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != 'page':
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    # Données annexes
    articles_qs   = Article.actifs.all().order_by('nom')
    articles_data = list(articles_qs.values('id', 'nom', 'prix_achat'))
    total_achats  = sum(a.total for a in Achat.actifs.select_related('paiement'))

    # 🔁 mode d’affichage (session dédiée aux achats)
    display_mode = resolve_display_mode(request, session_key="display_achats", default="cards")

    return {
        'achats': page_obj.object_list,
        'page_obj': page_obj,
        'total_achats': total_achats,
        'articles': articles_data,
        'caisses': Caisse.actifs.all(),
        'today': date.today().isoformat(),
        'filter_article': article_id,
        'date_filter': date_filter,
        'filter_paiement': paiement_id,
        'extra_querystring': extra_querystring,
        'is_admin': is_admin(request.user),
        'display_mode': display_mode,
    }

@login_required
@admin_required
def achats_list(request):
    context = build_achats_context(request)
    return render(request, 'achats/achats_list.html', context)

@login_required
@admin_required
def achats_list_partial(request):
    context = build_achats_context(request)

    # Si accès direct sans HTMX → renvoyer la page complète
    if request.headers.get('HX-Request') != 'true':
        return render(request, 'achats/achats_list.html', context)

    # Sinon, renvoyer seulement le wrapper (table/cards)
    return render(request, 'achats/includes/achats_list_wrapper.html', context)

@login_required
@admin_required
def achat_detail(request, pk):
    achat = get_object_or_404(Achat, pk=pk)
    return render(request, 'achats/achat_details.html', {'achat': achat})

def achat_detail_modal(request, pk):
    achat = get_object_or_404(Achat, pk=pk)
    html = render_to_string("achats/includes/achat_detail_modal_content.html", {"achat": achat}, request=request)
    return JsonResponse({"html": html})

@login_required
@admin_required
def achat_add(request):
    if request.method == "POST":
        article_ids = request.POST.getlist('article')
        quantites = request.POST.getlist('quantite')
        pus = request.POST.getlist('pu')
        remarque = request.POST.get('remarque', '')
        date = request.POST.get('date')
        num_facture = request.POST.get('num_facture', '')
        paiement_id = request.POST.get('paiement')
        paiement = Caisse.objects.get(id=paiement_id) if paiement_id else None

        achat = Achat.objects.create(
            date=date,
            remarque=remarque,
            num_facture=num_facture,
            paiement=paiement
        )

        for i in range(len(article_ids)):
            try:
                article = Article.objects.get(id=article_ids[i])
                pu = int(pus[i]) if pus[i].isdigit() else int(article.prix_achat)
                quantite = int(quantites[i]) if quantites[i].isdigit() else 0
                montant = pu * quantite
                LigneAchat.objects.create(achat=achat, article=article, pu=pu, quantite=quantite, montant=montant)
            except Article.DoesNotExist:
                continue

        messages.success(request, "Achat ajouté avec succès.")
        return redirect('achats_list')

    # si on accède en GET par erreur (normalement ce sera via modal sur la liste)
    return redirect('achats_list')

# Édition
@login_required
@admin_required
def achat_edit(request, pk):
    achat = get_object_or_404(Achat, pk=pk)
    if achat.statut_publication == "supprimé":
        messages.warning(request, "Cet achat a été supprimé et ne peut pas être modifié.")
        return redirect('achats_list')
    articles = Article.actifs.all().order_by('nom')

    # JSON pour le script JS
    articles_json = json.dumps([
        {
            "id": article.id,
            "nom": article.nom,
            "prix_achat": article.prix_achat
        }
        for article in articles
    ])

    if request.method == 'POST':
        form = AchatForm(request.POST, instance=achat)
        if form.is_valid():
            form.save()

            # Supprimer les anciennes lignes
            achat.lignes_achats.all().delete()

            # Récupérer les données des lignes du formulaire
            article_ids = request.POST.getlist('article')
            quantites = request.POST.getlist('quantite')
            pus = request.POST.getlist('pu')

            for i in range(len(article_ids)):
                try:
                    article = Article.objects.get(id=article_ids[i])
                    pu = int(pus[i]) if pus[i].isdigit() else int(article.prix_achat)
                    quantite = int(quantites[i]) if quantites[i].isdigit() else 0
                    montant = pu * quantite
                    LigneAchat.objects.create(
                        achat=achat,
                        article=article,
                        pu=pu,
                        quantite=quantite,
                        montant=montant
                    )
                except Article.DoesNotExist:
                    continue  # ignore invalid article IDs

            return redirect('achat_detail', pk=achat.pk)

    else:
        form = AchatForm(instance=achat)

    context = {
        "form": form,
        "achat": achat,
        "articles": articles,
        'caisses' : Caisse.actifs.all(),
        "articles_json": articles_json,
        "date": achat.date.isoformat(),
        "num_facture": achat.num_facture,
        "remarque": achat.remarque,
    }

    return render(request, 'achats/achat_edit.html', context)

# Suppression
@login_required
@admin_required
def achat_delete(request, pk):
    achat = get_object_or_404(Achat, pk=pk)
    if achat.statut_publication == "supprimé":
        messages.warning(request, "Cet achat est déjà supprimé.")
        return redirect('achats_list')

    if request.method == 'POST':
        # achat.delete()
        achat.soft_delete(user=request.user)
        return redirect('achats_list')  # à adapter selon ta vue de liste
    return render(request, 'achats/achat_confirm_delete.html', {'achat': achat})

# Suppression définitive
@login_required
@admin_required
def achat_delete_definitive(request, pk):
    achat = get_object_or_404(Achat, pk=pk)

    if request.method == 'POST':
        password = request.POST.get('password')
        user = authenticate(username=request.user.username, password=password)

        if user is None:
            messages.warning(request, "Mot de passe incorrect. Suppression annulée.")
            return redirect('achats_list')

        achat.delete()
        messages.success(request, "Achat supprimé définitivement avec succès.")
        return redirect('achats_list')

    return render(request, 'achats/achat_confirm_delete.html', {'achat': achat})

@require_POST
@login_required
@admin_required
def achat_restore(request, pk):
    achat = get_object_or_404(Achat, pk=pk)

    if achat.statut_publication != "supprimé":
        messages.info(request, "Cet achat n'est pas supprimé.")
        return redirect("achats_list")

    password = request.POST.get('password')
    user = authenticate(username=request.user.username, password=password)

    if user is None:
        messages.warning(request, "Mot de passe incorrect. Restauration annulée.")
        return redirect("achats_list")

    achat.restore(user=request.user)
    messages.success(request, "Achat restauré avec succès.")
    return redirect("achats_list")
