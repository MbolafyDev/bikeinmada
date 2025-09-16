# articles/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import QueryDict
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate
from django.db.models.deletion import ProtectedError

from common.decorators import admin_required
from common.utils import is_admin, resolve_display_mode

from .models import Article, Service, Taille, Couleur, Categorie
from .forms import ArticleForm, ServiceForm


def build_articles_context(request):
    articles = Article.objects.all().order_by('nom')

    # Filtres
    query = request.GET.get('q', '').strip()
    prix_min = request.GET.get('prix_min')
    prix_max = request.GET.get('prix_max')
    livraison = request.GET.get('livraison')

    if query:
        articles = articles.filter(nom__icontains=query)

    if prix_min:
        try:
            articles = articles.filter(prix_vente__gte=int(prix_min))
        except ValueError:
            pass

    if prix_max:
        try:
            articles = articles.filter(prix_vente__lte=int(prix_max))
        except ValueError:
            pass

    if livraison in ['Gratuite', 'Payante']:
        articles = articles.filter(livraison=livraison)

    # Pagination
    paginator = Paginator(articles, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # QS propre (sans page vide)
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != 'page':
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    # Mode d’affichage (GET > session > défaut)
    display_mode = resolve_display_mode(request, session_key="display_articles", default="cards")

    # 👇 Injecter les listes pour les <select> des modaux
    tailles = Taille.objects.all().order_by('taille')
    couleurs = Couleur.objects.all().order_by('couleur')
    categories = Categorie.objects.all().order_by('categorie')

    return {
        'articles': page_obj.object_list,
        'page_obj': page_obj,
        'query': query,
        'prix_min': prix_min,
        'prix_max': prix_max,
        'livraison_filter': livraison,
        'extra_querystring': extra_querystring,
        'display_mode': display_mode,
        'is_admin': is_admin(request.user),

        # 👇 pour les modaux (create/edit)
        'tailles': tailles,
        'couleurs': couleurs,
        'categories': categories,
    }


@login_required
def article_list(request):
    context = build_articles_context(request)
    return render(request, 'articles/articles_list.html', context)


@login_required
def article_list_partial(request):
    context = build_articles_context(request)
    if request.headers.get('HX-Request') != 'true':
        return render(request, 'articles/articles_list.html', context)
    return render(request, 'articles/includes/articles_list_wrapper.html', context)


@admin_required
def article_create(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            # ⚠️ Au cas où ArticleForm n’a pas (taille, couleur, categorie)
            article = form.save(commit=False)
            article.taille_id = request.POST.get('taille') or None
            article.couleur_id = request.POST.get('couleur') or None
            article.categorie_id = request.POST.get('categorie') or None
            article.save()
            messages.success(request, "Article créé avec succès.")
            return redirect('article_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    return redirect('article_list')


@admin_required
def article_edit(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            article = form.save(commit=False)
            # idem : sécuriser l’affectation des FK
            article.taille_id = request.POST.get('taille') or None
            article.couleur_id = request.POST.get('couleur') or None
            article.categorie_id = request.POST.get('categorie') or None
            article.save()
            messages.success(request, "Article modifié avec succès.")
            return redirect('article_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    return redirect('article_list')


@admin_required
def article_delete(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if request.method == 'POST':
        article.soft_delete(user=request.user)
        messages.success(request, "Article supprimé temporairement.")
    return redirect('article_list')


@admin_required
def article_delete_definitive(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if request.method == 'POST':
        password = request.POST.get('password')
        user = authenticate(username=request.user.username, password=password)
        if user is not None:
            try:
                article.delete()
                messages.success(request, f"L’article « {article.nom} » a été supprimé définitivement.")
            except ProtectedError:
                messages.warning(
                    request,
                    f"L’article « {article.nom} » ne peut pas être supprimé définitivement car il est lié à des commandes existantes."
                )
        else:
            messages.warning(request, "Mot de passe incorrect. Suppression annulée.")
    return redirect('article_list')


@admin_required
def article_restore(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if request.method == 'POST':
        password = request.POST.get('password')
        user = authenticate(username=request.user.username, password=password)
        if user is not None:
            article.restore(user=request.user)
            messages.success(request, f"L’article « {article.nom} » a été restauré avec succès.")
        else:
            messages.warning(request, "Mot de passe incorrect. Restauration annulée.")
    return redirect('article_list')


# ---- Services (inchangé) ----
@login_required
def service_list(request):
    services = Service.objects.all()
    query = request.GET.get('q', '')
    tarif_min = request.GET.get('tarif_min')
    tarif_max = request.GET.get('tarif_max')

    if query:
        services = services.filter(nom__icontains=query)

    if tarif_min:
        try:
            services = services.filter(tarif__gte=int(tarif_min))
        except ValueError:
            pass

    if tarif_max:
        try:
            services = services.filter(tarif__lte=int(tarif_max))
        except ValueError:
            pass

    paginator = Paginator(services, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != 'page':
            clean_params.setlist(key, clean_values)

    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    return render(request, 'articles/services_list.html', {
        'services': page_obj.object_list,
        'page_obj': page_obj,
        'query': query,
        'tarif_min': tarif_min,
        'tarif_max': tarif_max,
        'extra_querystring': extra_querystring,
    })


@admin_required
def service_create(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('service_list')
    else:
        form = ServiceForm()
    return redirect('service_list')


@admin_required
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('service_list')
    else:
        form = ServiceForm(instance=service)
    return redirect('service_list')


@admin_required
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        service.soft_delete(user=request.user)
        return redirect('service_list')
    return redirect('service_list')
