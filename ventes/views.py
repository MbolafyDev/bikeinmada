# zarastore/ventes/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.template.loader import get_template
from django.template.loader import render_to_string
from django.http import JsonResponse, HttpResponse, QueryDict
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate
from django.contrib import messages
from django.db.models import Sum, Prefetch
from django.core.paginator import Paginator
from django.db import transaction
from datetime import date
from weasyprint import HTML

from common.decorators import admin_required
from common.utils import is_admin, resolve_display_mode
from common.models import Pages, Caisse
from stocks.utils import calculer_stock_article

from .models import Commande, LigneCommande, Vente
from clients.models import Client
from articles.models import Article
from livraison.models import Livraison, Livreur
from .forms import VenteForm
from django.urls import reverse
from django.db.models import Q


import json

@login_required
def client_suggest(request):
    """
    GET /ventes/client-suggest/?q=xx
    Renvoie une petite liste des clients correspondant à q (>= 2 chars).
    """
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    # tu peux mettre istartswith pour resserrer, ou icontains pour être plus permissif
    qs = (Client.objects
          .filter(nom__icontains=q)
          .select_related('lieu')
          .order_by('-id')[:12])

    results = []
    for c in qs:
        results.append({
            'id': c.id,
            'nom': c.nom or '',
            'contact': c.contact or '',
            'reference_client': getattr(c, 'reference_client', '') or '',
            'lieu_id': c.lieu_id,
            'lieu': getattr(c.lieu, 'lieu', '') if getattr(c, 'lieu_id', None) else '',
            'precision_lieu': getattr(c, 'precision_lieu', '') or '',
        })
    return JsonResponse({'results': results})

def _get_existing_client(nom: str, contact: str):
    """
    Tente de retrouver un client existant en priorisant le contact (souvent unique).
    Fallback sur (nom, contact), puis sur nom seul.
    """
    qs = Client.objects.all()
    contact = (contact or '').strip()
    nom = (nom or '').strip()

    if contact:
        c = qs.filter(contact__iexact=contact).order_by('-id').first()
        if c:
            return c

    if nom and contact:
        c = qs.filter(nom__iexact=nom, contact__iexact=contact).order_by('-id').first()
        if c:
            return c

    if nom:
        return qs.filter(nom__iexact=nom).order_by('-id').first()

    return None


@login_required
def client_lookup(request):
    """
    GET /ventes/client-lookup/?nom=...&contact=...
    Retourne {found: bool, client: {...}} pour auto-compléter le formulaire.
    """
    q_nom = (request.GET.get('nom') or '').strip()
    q_contact = (request.GET.get('contact') or '').strip()

    client = _get_existing_client(q_nom, q_contact)
    if not client:
        return JsonResponse({'found': False})

    data = {
        'id': client.id,
        'nom': client.nom or '',
        'contact': client.contact or '',
        'reference_client': getattr(client, 'reference_client', '') or '',
        'lieu_id': client.lieu_id,
        'precision_lieu': getattr(client, 'precision_lieu', '') or '',
    }
    return JsonResponse({'found': True, 'client': data})


def build_commandes_context(request):
    commandes = (
        Commande.objects
        .select_related('client', 'page')
        .prefetch_related('lignes_commandes__article')
        .order_by('-date_livraison', '-numero_facture')
    )

    # Filtres
    date_livraison = request.GET.get('date_livraison')
    statut_vente = request.GET.get('statut_vente')
    statut_livraison = request.GET.get('statut_livraison')
    page_id = request.GET.get('page_id_filter')
    article_id = request.GET.get('article_id')

    if date_livraison:
        d = parse_date(date_livraison)
        if d:
            commandes = commandes.filter(date_livraison=d)
    if statut_vente:
        commandes = commandes.filter(statut_vente=statut_vente)
    if statut_livraison:
        commandes = commandes.filter(statut_livraison=statut_livraison)
    if page_id:
        commandes = commandes.filter(page_id=page_id)
    if article_id and article_id.strip():
        commandes = commandes.filter(lignes_commandes__article_id=article_id)

    # Totaux (hors annulée/supprimée/reportée)
    commandes_valides = commandes.exclude(statut_vente__in=["Annulée", "Supprimée", "Reportée"])
    total_montant = sum(c.montant_commande for c in commandes_valides)
    total_frais = commandes_valides.aggregate(total=Sum('frais_livraison'))['total'] or 0
    total_general = sum(c.total_commande() for c in commandes_valides)

    # Pagination
    paginator = Paginator(commandes, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Données nécessaires aux modals inclus (création commande)
    lieux = Livraison.actifs.all().order_by('lieu')

    # ⚠️ Corrigé : on précharge les FK + on sérialise categorie/taille/couleur en chaînes lisibles
    articles_qs = (
        Article.actifs
        .select_related('categorie', 'taille', 'couleur')
        .order_by('nom')
    )

    articles_data = []
    for a in articles_qs:
        articles_data.append({
            "id": a.id,
            "nom": a.nom or "",
            "categorie": (a.categorie.categorie if a.categorie else ""),
            "taille": (a.taille.taille if a.taille else ""),
            "couleur": (a.couleur.couleur if a.couleur else ""),
            "livraison": a.livraison or "",
            "prix_vente": int(getattr(a, "prix_vente", 0) or 0),
            "prix_achat": int(getattr(a, "prix_achat", 0) or 0),
            "stock": int(calculer_stock_article(a) or 0),
        })
    articles_json = json.dumps(articles_data, cls=DjangoJSONEncoder)

    date_du_jour = date.today().isoformat()

    # QS propre (préserve display, enlève page vide, etc.)
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != 'page':
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    display_mode = resolve_display_mode(request, session_key="display_commandes", default="table")

    return {
        'commandes': page_obj.object_list,
        'page_obj': page_obj,

        # Filtres (pour conserver les valeurs sélectionnées)
        'filtre_date_livraison': date_livraison or '',
        'filtre_statut_vente': statut_vente,
        'filtre_statut_livraison': statut_livraison,
        'filtre_page': page_id,
        'filtre_article_id': article_id,

        # Listes pour filtres et modals
        'articles': articles_qs,
        'pages': Pages.actifs.filter(type="VENTE"),
        'lieux': lieux,

        # Totaux
        'total_montant': total_montant,
        'total_frais': total_frais,
        'total_general': total_general,

        # Divers
        'extra_querystring': extra_querystring,
        'display_mode': display_mode,

        # Données JS pour le modal de création (✅ contient bien categorie/taille/couleur)
        'articles_json': articles_json,
        'date_du_jour': date_du_jour,
    }


@login_required
def liste_commandes(request):
    context = build_commandes_context(request)
    return render(request, 'ventes/journal_commandes.html', context)


@login_required
def liste_commandes_partial(request):
    context = build_commandes_context(request)

    # Si ce n'est pas un appel HTMX, renvoyer la page complète
    if request.headers.get('HX-Request') != 'true':
        return render(request, 'ventes/journal_commandes.html', context)

    return render(request, 'ventes/includes/commandes_list_wrapper.html', context)


@login_required
def detail_commande(request, commande_id):
    commande = get_object_or_404(Commande.objects.select_related('client'), id=commande_id)
    lignes = LigneCommande.objects.select_related('article').filter(commande=commande)
    montant_commande = sum(ligne.montant() for ligne in lignes)

    context = {
        'commande': commande,
        'lignes': lignes,
        'montant_commande': montant_commande,
    }
    return render(request, 'ventes/detail_commande.html', context)


@login_required
def creer_commande(request):
    # Jeux de données pour GET et pour (re)afficher le formulaire après erreur
    articles = (
        Article.actifs
        .select_related('categorie', 'taille', 'couleur')
        .order_by('nom')
    )
    pages = Pages.actifs.filter(type="VENTE")
    lieux = Livraison.actifs.all().order_by('lieu')

    if request.method == 'POST':
        # --- Récupération champs ---
        nom = (request.POST.get('nom') or '').strip()
        contact = (request.POST.get('contact') or '').strip()
        reference_client = (request.POST.get('reference_client') or '').strip()
        lieu_id = request.POST.get('lieu')
        precision_lieu = (request.POST.get('precision_lieu') or '').strip()
        remarque = (request.POST.get('remarque') or '').strip()

        date_commande = parse_date(request.POST.get('date_commande'))
        date_livraison = parse_date(request.POST.get('date_livraison'))
        date_debut_prestation = parse_date(request.POST.get('date_debut_prestation'))
        date_fin_prestation = parse_date(request.POST.get('date_fin_prestation'))

        try:
            frais_livreur = int(request.POST.get('frais_livreur') or 0)
        except (TypeError, ValueError):
            frais_livreur = 0

        try:
            frais_livraison = int(request.POST.get('frais_livraison') or 0)
        except (TypeError, ValueError):
            frais_livraison = 0

        page_id = request.POST.get('page')

        # --- Validations rapides ---
        if not nom or not contact or not lieu_id or not page_id:
            messages.error(request, "Merci de renseigner Nom, Contact, Lieu et Page.")
        else:
            # --- Récup objets liés ---
            lieu = get_object_or_404(Livraison, id=lieu_id)
            page = get_object_or_404(Pages, id=page_id)

            # --- Client : rechercher existant puis MAJ douce, sinon créer ---
            client = None
            # 1) priorité au contact (souvent unique)
            if contact:
                client = Client.objects.filter(contact__iexact=contact).order_by('-id').first()
            # 2) fallback (nom, contact)
            if not client and nom and contact:
                client = Client.objects.filter(nom__iexact=nom, contact__iexact=contact).order_by('-id').first()
            # 3) fallback nom seul
            if not client and nom:
                client = Client.objects.filter(nom__iexact=nom).order_by('-id').first()

            if client:
                # MAJ sans écraser avec des vides
                if nom and client.nom != nom:
                    client.nom = nom
                if contact and client.contact != contact:
                    client.contact = contact
                if reference_client:
                    client.reference_client = reference_client
                # on prend les valeurs fournies si présentes (sinon on garde l'existant)
                if lieu:
                    client.lieu = lieu
                if precision_lieu:
                    client.precision_lieu = precision_lieu
                client.save()
            else:
                client = Client.objects.create(
                    nom=nom,
                    contact=contact,
                    lieu=lieu,
                    precision_lieu=precision_lieu,
                    reference_client=reference_client
                )

            # --- Commande ---
            commande = Commande.objects.create(
                client=client,
                page=page,
                remarque=remarque,
                date_commande=date_commande or timezone.now().date(),
                date_livraison=date_livraison or timezone.now().date(),
                date_debut_prestation=date_debut_prestation or timezone.now().date(),
                date_fin_prestation=date_fin_prestation or timezone.now().date(),
                frais_livreur=frais_livreur,
                frais_livraison=frais_livraison,
            )

            # --- Lignes ---
            article_ids = request.POST.getlist('article')
            quantites   = request.POST.getlist('quantite')
            pu_list     = request.POST.getlist('pu')

            for i in range(len(article_ids)):
                if not article_ids[i]:
                    continue
                article = get_object_or_404(Article, pk=article_ids[i])

                try:
                    pu = int(pu_list[i] or 0)
                except (TypeError, ValueError):
                    pu = 0

                try:
                    qte = int(quantites[i] or 0)
                except (TypeError, ValueError):
                    qte = 0

                LigneCommande.objects.create(
                    commande=commande,
                    article=article,
                    prix_unitaire=pu,
                    prix_achat=article.prix_achat,
                    quantite=qte,
                )

            return redirect('commande_detail', commande_id=commande.id)

    # --- GET (ou POST invalide)
    # JSON articles pour le JS (valeurs lisibles pour les FK)
    articles_data = []
    for a in articles:
        articles_data.append({
            "id": a.id,
            "nom": a.nom or "",
            "categorie": (a.categorie.categorie if a.categorie else ""),
            "taille": (a.taille.taille if a.taille else ""),
            "couleur": (a.couleur.couleur if a.couleur else ""),
            "livraison": a.livraison or "",
            "prix_vente": int(getattr(a, "prix_vente", 0) or 0),
            "prix_achat": int(getattr(a, "prix_achat", 0) or 0),
            "stock": int(calculer_stock_article(a) or 0),
        })
    articles_json = json.dumps(articles_data, cls=DjangoJSONEncoder)
    date_du_jour = date.today().isoformat()

    return render(request, 'ventes/creer_commande.html', {
        'articles': articles,
        'pages': pages,
        'lieux': lieux,
        'articles_json': articles_json,
        'date_du_jour': date_du_jour,
    })


@login_required
def commande_edit(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)

    # Empêcher la modification si la commande est déjà payée
    if commande.statut_vente == "Payée":
        messages.warning(request, "Impossible de modifier une commande déjà payée.")
        return redirect('commande_detail', commande_id=commande.id)

    pages = Pages.actifs.filter(type="VENTE")
    lieux = Livraison.actifs.all().order_by('lieu')
    articles = (
        Article.actifs
        .select_related('categorie', 'taille', 'couleur')
        .order_by('nom')
    )
    for a in articles:
        a.stock = calculer_stock_article(a)

    if request.method == 'POST':
        # --- Récupération champs ---
        nom = (request.POST.get('nom') or '').strip()
        contact = (request.POST.get('contact') or '').strip()
        reference_client = (request.POST.get('reference_client') or '').strip()  # 🆕
        lieu_id = request.POST.get('lieu')
        precision_lieu = request.POST.get('precision_lieu') or ''
        remarque = request.POST.get('remarque') or ''

        date_commande = parse_date(request.POST.get('date_commande'))
        date_livraison = parse_date(request.POST.get('date_livraison'))
        date_debut_prestation = parse_date(request.POST.get('date_debut_prestation'))
        date_fin_prestation   = parse_date(request.POST.get('date_fin_prestation'))

        try:
            frais_livreur = int(request.POST.get('frais_livreur') or 0)
        except (TypeError, ValueError):
            frais_livreur = 0

        try:
            frais_livraison = int(request.POST.get('frais_livraison') or 0)
        except (TypeError, ValueError):
            frais_livraison = 0

        page_id = request.POST.get('page')

        # --- Validations minimales ---
        if not nom or not contact or not lieu_id or not page_id:
            messages.error(request, "Merci de renseigner Nom, Contact, Lieu et Page.")
        else:
            # --- MAJ objets liés ---
            commande.page = get_object_or_404(Pages, id=page_id)
            commande.date_commande = date_commande or commande.date_commande or timezone.now().date()
            commande.date_livraison = date_livraison or commande.date_livraison or timezone.now().date()

            # 🆕 champs prestation
            if date_debut_prestation:
                commande.date_debut_prestation = date_debut_prestation
            elif not commande.date_debut_prestation:
                commande.date_debut_prestation = timezone.now().date()

            if date_fin_prestation:
                commande.date_fin_prestation = date_fin_prestation
            elif not commande.date_fin_prestation:
                commande.date_fin_prestation = timezone.now().date()

            commande.remarque = remarque
            commande.frais_livreur = frais_livreur
            commande.frais_livraison = frais_livraison
            commande.save()

            # Client
            client = commande.client
            client.nom = nom
            client.contact = contact
            client.lieu = get_object_or_404(Livraison, id=int(lieu_id))
            client.precision_lieu = precision_lieu
            if reference_client:                      # 🆕 n’écrase que si une valeur est envoyée
                client.reference_client = reference_client  # 🆕
            client.save()

            # Lignes : on remplace proprement
            LigneCommande.objects.filter(commande=commande).delete()

            article_ids = request.POST.getlist('article')
            quantites   = request.POST.getlist('quantite')
            pu_list     = request.POST.getlist('pu')

            for i in range(len(article_ids)):
                if not article_ids[i]:
                    continue
                article = get_object_or_404(Article, pk=article_ids[i])

                try:
                    pu = int(pu_list[i] or 0)
                except (TypeError, ValueError):
                    pu = 0

                try:
                    qte = int(quantites[i] or 0)
                except (TypeError, ValueError):
                    qte = 0

                LigneCommande.objects.create(
                    commande=commande,
                    article=article,
                    prix_unitaire=pu,
                    prix_achat=article.prix_achat,
                    quantite=qte,
                )

            return redirect('commande_detail', commande_id=commande.id)

    # --- GET (ou POST invalide) : préparer contexte pour le template d’édition ---
    # Annoter le stock actuel pour affichage
    lignes = LigneCommande.objects.filter(commande=commande).select_related('article')
    for ligne in lignes:
        ligne.stock = calculer_stock_article(ligne.article)

    # Données articles pour JS (même format que créer commande)
    articles_data = [{
        "id": a.id,
        "nom": a.nom or "",
        "prix_vente": int(getattr(a, "prix_vente", 0) or 0),
        "prix_achat": int(getattr(a, "prix_achat", 0) or 0),
        "livraison": a.livraison or "",
        "stock": int(a.stock or 0),
        "taille": (a.taille.taille if a.taille else ""),
        "couleur": (a.couleur.couleur if a.couleur else ""),
        "categorie": (a.categorie.categorie if a.categorie else ""),
    } for a in articles]
    articles_json = json.dumps(articles_data, cls=DjangoJSONEncoder)

    return render(request, 'ventes/edit_commande.html', {
        'commande': commande,
        'pages': pages,
        'lignes': lignes,
        'articles': articles,
        'lieux': lieux,
        'articles_json': articles_json,
    })


@login_required
@admin_required
def commande_delete(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)

    # Empêcher la suppression si la commande est déjà payée ou livrée
    if commande.statut_vente == "Payée":
        messages.warning(request, "Impossible de supprimer une commande déjà payée.")
        return redirect('commande_detail', commande_id=commande.id)

    if commande.statut_livraison == "Livrée":
        messages.warning(request, "Impossible de supprimer une commande déjà livrée.")
        return redirect('commande_detail', commande_id=commande.id)

    if request.method == 'POST':
        # Mettre à jour les statuts
        commande.statut_vente = "Supprimée"
        commande.statut_livraison = "Supprimée"
        commande.save(update_fields=["statut_vente", "statut_livraison"])

        # Soft delete
        commande.soft_delete(user=request.user)
        messages.success(request, "Commande supprimée avec succès.")
        return redirect('liste_commandes')

    return redirect('liste_commandes')


@login_required
@admin_required
@require_POST
def commande_restore(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)
    password = request.POST.get('password')

    # Vérifier le mot de passe
    user = authenticate(username=request.user.username, password=password)
    if user is None:
        messages.warning(request, "Mot de passe incorrect. Restauration annulée.")
        return redirect('liste_commandes')

    # Restaurer les données
    commande.restore(user=request.user)
    commande.statut_vente = "En attente"
    commande.statut_livraison = "En attente"
    commande.save(update_fields=["statut_vente", "statut_livraison"])

    messages.success(request, f"La commande #{commande.numero_facture} a été restaurée avec succès.")
    return redirect('liste_commandes')


# --- Contexte pour le journal d'encaissement ---
def build_ventes_context(request):
    ventes = (
        Vente.objects
        .select_related('commande__client', 'commande__page', 'paiement')
        .prefetch_related('commande__lignes_commandes__article')
        .order_by('-commande__date_livraison', '-commande__numero_facture')
    )

    # Filtres GET
    date_livraison   = request.GET.get('date_livraison')    # format YYYY-MM-DD
    date_encaissement = request.GET.get('date_encaissement') # format YYYY-MM-DD
    paiement_id      = request.GET.get('paiement')
    page_id_filter   = request.GET.get('page_id_filter')

    if date_livraison:
        ventes = ventes.filter(commande__date_livraison=date_livraison)
    if date_encaissement:
        ventes = ventes.filter(date_encaissement=date_encaissement)
    if paiement_id:
        ventes = ventes.filter(paiement_id=paiement_id)
    if page_id_filter:
        ventes = ventes.filter(commande__page_id=page_id_filter)

    # Totaux (sur le queryset filtré, page non prise en compte pour ces totaux)
    total_ventes   = sum(v.montant for v in ventes)
    total_montant  = sum(v.commande.montant_commande for v in ventes)
    total_frais    = sum(v.commande.frais_livraison for v in ventes)

    # Pagination
    paginator   = Paginator(ventes, 24)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    # Forms pour les ventes de la page courante
    form_mod_dict = { v.id: VenteForm(instance=v) for v in page_obj.object_list }

    # QS propre (préserve paramètres sauf 'page' vide)
    params = request.GET.copy()
    clean = QueryDict(mutable=True)
    for key, values in params.lists():
        vals = [v for v in values if v.strip()]
        if vals and key != 'page':
            clean.setlist(key, vals)
    extra_querystring = '&' + clean.urlencode() if clean else ''

    # 🔁 mode d'affichage (session distincte pour ce journal)
    display_mode = resolve_display_mode(request, session_key="display_ventes", default="cards")

    return {
        'ventes': page_obj.object_list,
        'page_obj': page_obj,
        'total_ventes': total_ventes,
        'total_montant': total_montant,
        'total_frais': total_frais,
        'paiements': Caisse.actifs.all(),
        'date_livraison': date_livraison,
        'date_encaissement': date_encaissement,
        'paiement_id': paiement_id,
        'filtre_page': page_id_filter,
        'pages': Pages.actifs.filter(type="VENTE"),
        'extra_querystring': extra_querystring,
        'display_mode': display_mode,
        'form_mod_dict': form_mod_dict,
    }


@login_required
@admin_required
def journal_encaissement_ventes(request):
    context = build_ventes_context(request)
    return render(request, 'ventes/journal_encaissement.html', context)


@login_required
def journal_encaissement_ventes_partial(request):
    context = build_ventes_context(request)

    # Si accès direct sans HTMX: renvoyer la page complète (styles, offline, etc.)
    if request.headers.get('HX-Request') != 'true':
        return render(request, 'ventes/journal_encaissement.html', context)

    # Sinon, renvoyer juste le wrapper (table/cards)
    return render(request, 'ventes/includes/encaissement_list_wrapper.html', context)


@login_required
@admin_required
def encaissement_ventes(request):
    selected_date = request.GET.get("date_livraison")
    selected_statut_livraison = request.GET.get("statut_livraison")
    selected_statut_vente = request.GET.get("statut_vente")
    selected_livreur = request.GET.get("livreur")  # <-- nouveau

    # Base queryset + optimisations relationnelles
    commandes = (
        Commande.objects
        .select_related("client", "client__lieu", "livreur")
        .prefetch_related("lignes_commandes", "lignes_commandes__article")
        .order_by("date_livraison")
    )

    # Premier accès: valeurs par défaut
    if not request.GET:
        selected_statut_vente = "En attente"
        selected_statut_livraison = "Livrée"
        commandes = commandes.filter(
            statut_vente=selected_statut_vente,
            statut_livraison=selected_statut_livraison
        )
    else:
        if selected_statut_vente:
            commandes = commandes.filter(statut_vente=selected_statut_vente)

    if selected_date:
        commandes = commandes.filter(date_livraison=selected_date)

    if selected_statut_livraison:
        commandes = commandes.filter(statut_livraison=selected_statut_livraison)

    # 💡 Filtre livreur
    if selected_livreur:
        commandes = commandes.filter(livreur_id=selected_livreur)

    # Totaux généraux (hors pagination)
    total_montant = sum(c.montant_commande for c in commandes)
    total_frais = sum(c.frais_livraison or 0 for c in commandes)
    total_general = sum(c.total_commande() for c in commandes)
    total_frais_livreur = sum(c.frais_livreur or 0 for c in commandes)

    # Pagination
    paginator = Paginator(commandes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Reconstruction de la querystring sans 'page'
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if (v or "").strip()]
        if clean_values and key != 'page':
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    caisses = Caisse.actifs.all()
    today = timezone.now().date()
    livreurs = Livreur.objects.all().order_by("id")  # ajustez 'id' en 'nom' si dispo

    context = {
        'commandes': page_obj.object_list,
        'page_obj': page_obj,
        'extra_querystring': extra_querystring,
        'caisses': caisses,
        'today': today,

        'selected_date': selected_date or "",
        'selected_statut_livraison': selected_statut_livraison or "",
        'selected_statut_vente': selected_statut_vente or "",
        'selected_livreur': selected_livreur or "",

        'livreurs': livreurs,

        'total_montant': total_montant,
        'total_frais': total_frais,
        'total_general': total_general,
        'total_frais_livreur' : total_frais_livreur,
    }

    return render(request, 'ventes/encaissement_ventes.html', context)


@login_required
@admin_required
def encaissement_ventes_groupes(request):
    if request.method != 'POST':
        return redirect('encaissement_ventes')

    ids = request.POST.getlist('commandes')
    paiement_id = request.POST.get('paiement')
    date_encaissement = request.POST.get('date_encaissement')

    if not ids:
        messages.warning(request, "Aucune commande sélectionnée.")
        return redirect('encaissement_ventes')

    if not paiement_id:
        messages.warning(request, "Veuillez choisir un mode de paiement.")
        return redirect('encaissement_ventes')

    paiement = get_object_or_404(Caisse, pk=paiement_id)
    commandes = Commande.objects.filter(id__in=ids)

    # Vérification anti double encaissement
    deja_payees = commandes.filter(statut_vente="Payée")
    if deja_payees.exists():
        factures_err = ", ".join(
            c.numero_facture or f"Commande {c.id}" for c in deja_payees
        )
        messages.warning(
            request,
            f"Impossible d'encaisser : les commandes suivantes sont déjà payées ({factures_err})."
        )
        return redirect('encaissement_ventes')

    with transaction.atomic():
        for commande in commandes:
            Vente.objects.create(
                commande=commande,
                paiement=paiement,
                montant=commande.total_commande(),
                date_encaissement=date_encaissement
            )
            commande.statut_vente = 'Payée'
            commande.save()

    messages.success(
        request,
        f"{commandes.count()} vente(s) encaissée(s) avec succès. Statut vente mis à jour."
    )
    return redirect('encaissement_ventes')


@login_required
@admin_required
@require_http_methods(["POST"])
def vente_encaissement_edit(request, pk):
    vente = get_object_or_404(Vente, pk=pk)
    form = VenteForm(request.POST, instance=vente)
    if form.is_valid():
        form.save()
        messages.success(request, "Encaissement de vente modifiée avec succès.")
    else:
        messages.error(request, "Erreur lors de la modification de l'encaissement de vente.")
    return redirect('liste_encaissement_ventes')


@login_required
@admin_required
@require_http_methods(["POST"])
def vente_encaissement_delete(request, pk):
    password = request.POST.get("password")
    user = authenticate(username=request.user.username, password=password)

    if user is None:
        messages.warning(request, "Mot de passe incorrect. Suppression annulée.")
        return redirect('liste_encaissement_ventes')

    vente = get_object_or_404(Vente, pk=pk)
    commande = vente.commande
    commande.statut_vente = 'En attente'
    commande.save()
    vente.delete()

    messages.success(request, "Encaissement de vente supprimé avec succès.")
    return redirect('liste_encaissement_ventes')


@login_required
def facturation_commandes(request):
    params = request.GET.copy()
    selected_date = params.get("date")
    selected_statut = params.get("statut_livraison")

    # 1er chargement : statut par défaut
    if not request.GET:
        selected_statut = "Planifiée"

    commandes = Commande.objects.all().order_by('-date_livraison')

    if selected_date:
        parsed_date = parse_date(selected_date)
        if parsed_date:
            commandes = commandes.filter(date_livraison=parsed_date)

    if selected_statut:
        commandes = commandes.filter(statut_livraison=selected_statut)

    # Pagination
    paginator = Paginator(commandes, 24)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # QS propre (sans page)
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        if key != 'page':
            clean_values = [v for v in values if v.strip() or v == '']
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    display_mode = resolve_display_mode(request, session_key="display_facturation", default="cards")

    context = {
        "commandes": page_obj.object_list,
        "page_obj": page_obj,
        "selected_date": selected_date,
        "selected_statut": selected_statut,
        "extra_querystring": extra_querystring,
        "display_mode": display_mode,
    }
    return render(request, "ventes/facturation_commandes.html", context)


@login_required
def facturation_commandes_partial(request):
    # ⚠️ Attention : si tu veux être 100% safe ici, il faut reconstruire le contexte
    # comme dans facturation_commandes() (render() ne donne pas .context_data).
    # Tu as laissé ce comportement : on le conserve pour ne pas changer ton flux.
    ctx = facturation_commandes(request).context_data  # commentaire d'origine
    return render(request, "ventes/includes/facturation_list_wrapper.html", ctx)


@login_required
@require_http_methods(["POST"])
def voir_factures(request):
    ids = request.POST.getlist("commandes")

    lignes_qs = LigneCommande.objects.select_related("article").order_by("id")

    commandes = (
        Commande.objects
        .filter(id__in=ids)
        .select_related("client", "page", "vente__paiement")
        .prefetch_related(Prefetch("lignes_commandes", queryset=lignes_qs))
    )

    return render(request, "ventes/factures.html", {"commandes": commandes})


@login_required
def imprimer_factures(request):
    if request.method == 'POST':
        ids = request.POST.getlist('commandes')
        if not ids:
            return redirect('facturation_commande')
        commandes = Commande.objects.filter(id__in=ids)
        return render(request, 'ventes/factures.html', {
            'commandes': commandes,
            'impression': True,  # on peut aussi utiliser request.GET.get("print")
        })
    return redirect('facturation_commande')


@login_required
def factures_pdf(request):
    if request.method == 'POST':
        ids = request.POST.getlist('commandes')
        commandes = Commande.objects.filter(id__in=ids)

        # Chargement du template
        template = get_template('ventes/factures.html')
        html_string = template.render({'commandes': commandes})

        # Création de la réponse HTTP
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="factures.pdf"'

        # Conversion HTML -> PDF
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)

        return response


@login_required
def mise_a_jour_statuts_ventes(request):
    today = timezone.now().date()

    params = request.GET.copy()
    date_commande = params.get('date_commande')
    statut_vente = params.get('statut_vente', 'Annulée')

    commandes_qs = Commande.objects.all()

    if date_commande:
        commandes_qs = commandes_qs.filter(date_commande=date_commande)
    if statut_vente:
        commandes_qs = commandes_qs.filter(statut_vente=statut_vente)

    commandes_qs = commandes_qs.order_by('-date_commande')

    paginator = Paginator(commandes_qs, 20)
    page_number = params.get("page")
    page_obj = paginator.get_page(page_number)

    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        if key != "page":
            clean_params.setlist(key, values)
    if 'statut_vente' not in params:
        clean_params['statut_vente'] = statut_vente
    extra_querystring = clean_params.urlencode()

    return render(request, 'ventes/mise_a_jour_statuts_vente.html', {
        'commandes': page_obj,
        'page_obj': page_obj,
        'extra_querystring': extra_querystring,
        'date_commande': date_commande,
        'statut_vente': statut_vente,
        'today': today,
        'is_admin': is_admin(request.user),
    })


@login_required
def mise_a_jour_statuts_ventes_groupes(request):
    if request.method == 'POST':
        ids = request.POST.getlist('commandes')
        action = request.POST.get('action')

        if not ids:
            messages.warning(request, "Aucune commande sélectionnée.")
            return redirect('mise_a_jour_statuts_ventes')

        commandes = Commande.objects.filter(id__in=ids)

        if action == 'en_attente':
            commandes.update(statut_vente='En attente', statut_livraison='En attente')
            messages.success(request, f"{commandes.count()} commande(s) mises en attente.")
        elif action == 'annulée':
            commandes.update(statut_vente='Annulée', statut_livraison='Annulée')
            messages.success(request, f"{commandes.count()} commande(s) annulée(s).")
        else:
            messages.error(request, "Action non reconnue.")

        return redirect('mise_a_jour_statuts_ventes')
