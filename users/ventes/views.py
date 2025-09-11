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
from django.db.models import Sum
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
import json

def build_commandes_context(request):
    commandes = Commande.objects \
        .select_related('client', 'page') \
        .prefetch_related('lignes_commandes__article') \
        .order_by('-date_livraison', '-numero_facture')

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
        'filtre_date_livraison': date_livraison or '',
        'filtre_statut_vente': statut_vente,
        'filtre_statut_livraison': statut_livraison,
        'filtre_page': page_id,
        'filtre_article_id': article_id,
        'articles': Article.actifs.all().order_by('nom'),
        'pages': Pages.actifs.filter(type="VENTE"),
        'total_montant': total_montant,
        'total_frais': total_frais,
        'total_general': total_general,
        'extra_querystring': extra_querystring,
        'display_mode': display_mode,
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
        # ou: return redirect('liste_commandes')

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

# @login_required
# def commande_detail_ajax(request, commande_id):
#     commande = get_object_or_404(Commande.objects.select_related('client'), id=commande_id)
#     lignes = LigneCommande.objects.select_related('article').filter(commande=commande)
#     montant_commande = sum(ligne.montant() for ligne in lignes)

#     html = render_to_string('ventes/includes/detail_commande_modal.html', {
#         'commande': commande,
#         'lignes': lignes,
#         'montant_commande': montant_commande,
#     }, request=request)

#     return JsonResponse({'html': html})

@login_required
def creer_commande(request):
    articles = Article.actifs.all().order_by('nom')
    pages = Pages.actifs.filter(type="VENTE")
    lieux = Livraison.actifs.all().order_by('lieu')

    if request.method == 'POST':
        # Récupération des données 
        nom = request.POST.get('nom')
        lieu_id = request.POST.get('lieu')
        precision_lieu = request.POST.get('precision_lieu')
        contact = request.POST.get('contact')
        remarque = request.POST.get('remarque')
        date_commande = request.POST.get('date_commande')
        date_livraison = request.POST.get('date_livraison')
        frais_livreur = request.POST.get('frais_livreur')
        frais_livraison = request.POST.get('frais_livraison')

        # Récupération de l'objet Livraison correspondant
        lieu = get_object_or_404(Livraison, id=lieu_id)

        # Création ou récupération du client
        client, created = Client.objects.get_or_create(
            nom=nom,
            contact=contact,
            defaults={'lieu': lieu, 'precision_lieu': precision_lieu}
        )

        if not created:
            client.lieu = lieu
            client.precision_lieu = precision_lieu
            client.save()

        # Création de la commande
        page_id = request.POST.get('page')
        page = Pages.objects.get(id=page_id)

        commande = Commande.objects.create(
            client=client,
            page=page,
            remarque=remarque,
            date_commande=date_commande,
            date_livraison=date_livraison,
            frais_livreur = frais_livreur,
            frais_livraison = frais_livraison,
        )

        # Traitement des lignes de commande
        article_ids = request.POST.getlist('article')
        quantites = request.POST.getlist('quantite')
        pu_list = request.POST.getlist('pu')
        prix_achat_list = request.POST.getlist('prix_achat')
        # frais_list = request.POST.getlist('livraison')

        for i in range(len(article_ids)):
            article = Article.objects.get(pk=article_ids[i])
            pu = int(pu_list[i])
            prix_achat = article.prix_achat
            qte = int(quantites[i])
            # frais = float(frais_list[i])

            LigneCommande.objects.create(
                commande=commande,
                article=article,
                prix_unitaire=pu,
                prix_achat=prix_achat,
                quantite=qte,
                # livraison=frais
            )

        return redirect('commande_detail', commande_id=commande.id)

    # Ajout du stock actuel de chaque article
    articles_data = []
    for article in articles:
        stock = calculer_stock_article(article)
        articles_data.append({
            'id': article.id,
            'nom': article.nom,
            'prix_vente': article.prix_vente,
            'prix_achat': article.prix_achat,
            'livraison': article.livraison,
            'stock': stock,
        })
    # Sérialisation des articles pour JS
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
    lieux = Livraison.actifs.all()
    articles = Article.actifs.all().order_by('nom')

    articles_json = json.dumps([
        {
            "id": article.id,
            "nom": article.nom,
            "prix_vente": int(article.prix_vente),
            "prix_achat": int(article.prix_achat),
            "livraison": article.livraison,
            "stock": calculer_stock_article(article),
        }
        for article in articles
    ])

    if request.method == 'POST':
        page_id = request.POST.get('page')
        commande.page = get_object_or_404(Pages, id=page_id)
        commande.date_commande = request.POST.get('date_commande') or timezone.now()
        commande.date_livraison = request.POST.get('date_livraison')
        commande.remarque = request.POST.get('remarque')
        commande.frais_livreur = request.POST.get('frais_livreur') or 0
        commande.frais_livraison = request.POST.get('frais_livraison') or 0
        commande.save()

        client = commande.client
        client.nom = request.POST.get('nom')
        client.contact = request.POST.get('contact')
        lieu_id = request.POST.get('lieu')
        client.lieu = get_object_or_404(Livraison, id=int(lieu_id))
        client.precision_lieu = request.POST.get('precision_lieu')
        client.save()

        LigneCommande.objects.filter(commande=commande).delete()

        article_ids = request.POST.getlist('article')
        quantites = request.POST.getlist('quantite')
        pu_list = request.POST.getlist('pu')
        prix_achat_list  = request.POST.getlist('prix_achat')

        for i in range(len(article_ids)):
            article = get_object_or_404(Article, pk=article_ids[i])
            pu = float(pu_list[i])
            qte = int(quantites[i])
            prix_achat = article.prix_achat

            LigneCommande.objects.create(
                commande = commande,
                article = article,
                prix_unitaire = pu,
                prix_achat = prix_achat,
                quantite = qte,
            )

        return redirect('commande_detail', commande_id=commande.id)

    lignes = LigneCommande.objects.filter(commande=commande)
    for ligne in lignes:
        ligne.stock = calculer_stock_article(ligne.article)

    return render(request, 'ventes/modifier_commande.html', {
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
    ventes = Vente.objects.select_related('commande__client', 'commande__page', 'paiement') \
                          .prefetch_related('commande__lignes_commandes__article') \
                          .order_by('-commande__date_livraison', '-commande__numero_facture')

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
        'selected_livreur': selected_livreur or "",   # <-- nouveau

        'livreurs': livreurs,                         # <-- nouveau

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
    # Retourne uniquement le wrapper (HTMX)
    ctx = facturation_commandes(request).context_data  # render() → TemplateResponse; .context_data dispo
    return render(request, "ventes/includes/facturation_list_wrapper.html", ctx)

@login_required
@require_http_methods(["POST"])
def voir_factures(request):
    ids = request.POST.getlist("commandes")
    commandes = Commande.objects.filter(id__in=ids)
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
