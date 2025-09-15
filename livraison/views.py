from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse, QueryDict
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from common.decorators import admin_required
from common.utils import is_admin, resolve_display_mode
from django.db.models import Q, Sum, F, IntegerField, Value, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.db import transaction
from .models import Livreur, Livraison, CATEGORIE_CHOIX, FRAIS_LIVRAISON_PAR_DEFAUT, FRAIS_LIVREUR_PAR_DEFAUT
from common.models import Caisse, PlanDesComptes
from ventes.models import Commande, LigneCommande
from charges.models import Charge
from .forms import LivreurForm
from datetime import datetime
from django.contrib.auth import authenticate

def _check_password(request) -> bool:
    """Vérifie le mot de passe saisi dans un POST (champ 'password')."""
    password = (request.POST.get("password") or "").strip()
    if not password:
        return False
    user = authenticate(username=request.user.username, password=password)
    return user is not None


@login_required
def liste_livraisons(request): 
    livreurs = Livreur.objects.all()
    lieux = Livraison.objects.order_by('lieu')
    commandes = Commande.objects.order_by('-date_livraison')

    livreur_id = request.GET.get('livreur')
    selected_date = request.GET.get('date')
    selected_statut = request.GET.get('statut_livraison')

    # Défault sur 1er chargement (pas de page explicite ET pas de statut choisi)
    if request.GET.get("page") is None and selected_statut is None:
        selected_statut = "Planifiée"

    # Filtres
    if livreur_id:
        commandes = commandes.filter(livreur_id=livreur_id)
    if selected_date:
        d = parse_date(selected_date)
        if d:
            commandes = commandes.filter(date_livraison=d)
    if selected_statut:
        commandes = commandes.filter(statut_livraison=selected_statut)

    # Pagination
    paginator = Paginator(commandes, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # QS propre
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != 'page':
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    display_mode = resolve_display_mode(request, session_key="display_livraisons", default="cards")

    return render(request, 'livraison/liste_livraisons.html', {
        'commandes': page_obj.object_list,
        'page_obj': page_obj,
        'livreurs': livreurs,
        'lieux': lieux,
        'selected_livreur': livreur_id,
        'selected_date': selected_date,
        'selected_statut': selected_statut,
        'extra_querystring': extra_querystring,
        'is_admin': is_admin(request.user),
        'display_mode': display_mode,
    })

@login_required
def liste_livraisons_partial(request):
    # même contexte que la page complète
    response = liste_livraisons(request)
    context = response.context_data if hasattr(response, "context_data") else response.context_data  # Django 4: HttpResponse n'a pas context
    # On renvoie le wrapper si c'est bien une requête HTMX, sinon la page complète
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'livraison/includes/livraisons_list_wrapper.html', context)
    return response

@login_required
def modifier_livraison(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)
    if request.method == 'POST':
        livreur_id = request.POST.get('livreur')
        frais = request.POST.get('frais_livreur')

        if livreur_id and frais:
            commande.livreur_id = livreur_id
            commande.frais_livreur = int(frais)
            commande.save()
            messages.success(request, "Livraison mise à jour avec succès.")
        else:
            messages.error(request, "Veuillez remplir tous les champs.")
    return redirect('liste_livraisons')

@login_required
def fiche_livraison(request):
    livreur_id = request.GET.get('livreur')
    date_str = request.GET.get('date')
    
    if not livreur_id or not date_str:
        return HttpResponse("Paramètres manquants", status=400)
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return HttpResponse("Date invalide", status=400)

    livreur = get_object_or_404(Livreur, id=livreur_id)
    commandes = Commande.objects.filter(
        livreur=livreur,
        date_livraison=date,
        statut_livraison = "Planifiée"
    ).select_related('client').prefetch_related('lignes_commandes__article')

    total_general = sum(c.total_commande() for c in commandes)

    return render(request, 'livraison/fiche_livraison.html', {
        'livreur': livreur,
        'commandes': commandes,
        'date': date,
        'total_general': total_general,
        "is_admin": is_admin(request.user),
    })

@login_required
def fiche_de_suivi(request):
    livreur_id = request.GET.get('livreur')
    date_str = request.GET.get('date')
    
    if not livreur_id or not date_str:
        return HttpResponse("Paramètres manquants", status=400)
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return HttpResponse("Date invalide", status=400)

    livreur = get_object_or_404(Livreur, id=livreur_id)
    commandes = Commande.objects.filter(
        livreur=livreur,
        date_livraison=date,
    ).exclude(statut_livraison="Supprimée") \
     .select_related('client') \
     .prefetch_related('lignes_commandes__article')

    # ➜ on ne compte pas les commandes « Annulée » ou « Reportée »
    total_general = sum(
        c.total_commande() if c.statut_livraison not in ["Annulée", "Reportée", "Supprimée"] else 0
        for c in commandes
    )

    # ➜ Total des frais livreur (même logique)
    total_frais_livreur = sum(
        (c.frais_livreur or 0) if c.statut_livraison not in ["Annulée", "Reportée", "Supprimée"] else 0
        for c in commandes
    )

    reste_versement = total_general - total_frais_livreur

    return render(request, 'livraison/fiche_de_suivi.html', {
        'livreur': livreur,
        'commandes': commandes,
        'date': date,
        'total_general': total_general,
        'total_frais_livreur': total_frais_livreur,
        'reste_versement': reste_versement,
        "is_admin": is_admin(request.user),
    })

@login_required
def planification_livraison(request):
    livreurs = Livreur.objects.all()
    commandes_qs = Commande.objects.order_by('-date_livraison')

    params = request.GET.copy()
    livreur_id = params.get('livreur')
    date = params.get('date')
    statut_livraison = params.get('statut_livraison')

    if 'statut_livraison' not in params:
        statut_livraison = "En attente"

    commandes_qs = Commande.objects.order_by('-date_livraison')

    if statut_livraison:
        commandes_qs = commandes_qs.filter(statut_livraison=statut_livraison)
    if livreur_id:
        commandes_qs = commandes_qs.filter(livreur_id=livreur_id)
    if date:
        commandes_qs = commandes_qs.filter(date_livraison=date)

    paginator = Paginator(commandes_qs, 24)
    page_number = params.get("page")
    page_obj = paginator.get_page(page_number)

    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        if key != "page":
            clean_params.setlist(key, values)

    # Si statut_livraison absent, on ajoute la valeur par défaut pour l'URL
    if 'statut_livraison' not in params:
        clean_params['statut_livraison'] = statut_livraison

    extra_querystring = clean_params.urlencode()

    return render(request, 'livraison/planification_livraison.html', {
        'commandes': page_obj.object_list,
        'livreurs': livreurs,
        'selected_livreur': livreur_id,
        'selected_date': date,
        'selected_statut': statut_livraison,
        'page_obj': page_obj,
        'extra_querystring': extra_querystring,
        "is_admin": is_admin(request.user),
    })

@login_required
def assigner_livreur_groupes(request):
    if request.method == 'POST':
        ids = request.POST.getlist('commandes')
        livreur_id = request.POST.get('livreur_id')
        date_livraison = request.POST.get('date_livraison')

        if not ids:
            messages.warning(request, "Aucune commande sélectionnée.")
            return redirect('planification_livraison')

        if not livreur_id or not date_livraison:
            messages.warning(request, "Veuillez choisir un livreur et une date de livraison.")
            return redirect('planification_livraison')

        livreur = get_object_or_404(Livreur, pk=livreur_id)
        commandes = Commande.objects.filter(id__in=ids)

        frais_remis_zero = False

        for commande in commandes:
            commande.livreur = livreur
            commande.date_livraison = date_livraison
            commande.statut_livraison = 'Planifiée'

             # ✅ Remettre frais à zéro si livreur est un employé
            if livreur.type == 'Employé':
                commande.frais_livreur = 0
                commande.paiement_frais_livreur = "N/A"
                frais_remis_zero = True
                
            commande.save()

        messages.success(
            request,
            f"{commandes.count()} commande(s) assignée(s) à {livreur.nom} pour le {date_livraison}."
        )

        if frais_remis_zero:
            messages.info(request, "Le(s) frais livreur a (ont) été mis à zéro car le livreur est un employé.")

        return redirect('planification_livraison')

@login_required
def mise_a_jour_statuts_livraisons(request):
    today = timezone.now().date()

    params = request.GET.copy()
    date_livraison = params.get('date_livraison')
    livreur_id = params.get('livreur')
    statut_livraison = params.get('statut_livraison')
    if 'statut_livraison' not in params:
        statut_livraison = "Planifiée"

    commandes_qs = Commande.objects.all()

    if date_livraison:
        commandes_qs = commandes_qs.filter(date_livraison=date_livraison)
    if livreur_id:
        commandes_qs = commandes_qs.filter(livreur_id=livreur_id)
    if statut_livraison:
        commandes_qs = commandes_qs.filter(statut_livraison=statut_livraison)

    # --- IMPORTANT : annotations pour éviter N+1 et pouvoir agréger ---
    # montant_commande = SUM(lignes.prix_unitaire * lignes.quantite)
    commandes_qs = commandes_qs.annotate(
        montant_commande_anno=Coalesce(
            Sum(F('lignes_commandes__prix_unitaire') * F('lignes_commandes__quantite')),
            Value(0),
        ),
        total_commande_anno=ExpressionWrapper(
            F('montant_commande_anno') + Coalesce(F('frais_livraison'), Value(0)),
            output_field=IntegerField(),
        ),
    ).order_by('-date_livraison')

    # --- Agrégats sur l'ensemble filtré (toutes pages) ---
    agg = commandes_qs.aggregate(
        total_filtre_total_commande=Coalesce(Sum('total_commande_anno'), Value(0)),
        total_filtre_frais_livreur=Coalesce(Sum('frais_livreur'), Value(0)),
    )

    # Pagination (garder le même QS annoté)
    paginator = Paginator(commandes_qs, 24)
    page_number = params.get("page")
    page_obj = paginator.get_page(page_number)

    # Querystring propre pour la pagination
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        if key != "page":
            clean_params.setlist(key, values)
    if 'statut_livraison' not in params:
        clean_params['statut_livraison'] = statut_livraison
    extra_querystring = clean_params.urlencode()

    livreurs = Livreur.objects.all()

    return render(request, 'livraison/mise_a_jour_statuts.html', {
        'commandes': page_obj,
        'page_obj': page_obj,
        'extra_querystring': extra_querystring,
        'livreurs': livreurs,
        'date_livraison': date_livraison,
        'selected_livreur': livreur_id,
        'statut_livraison': statut_livraison,
        'today': today,
        'is_admin': is_admin(request.user),

        # 🔢 Totaux globaux (toutes pages, avec filtres existants)
        'total_filtre_total_commande': int(agg['total_filtre_total_commande'] or 0),
        'total_filtre_frais_livreur': int(agg['total_filtre_frais_livreur'] or 0),
    })

def mise_a_jour_statuts_livraisons_groupes(request):
    if request.method != 'POST':
        return redirect('mise_a_jour_statuts_livraisons')

    ids = request.POST.getlist('commandes')
    action = request.POST.get('action')
    nouvelle_date = request.POST.get('nouvelle_date')

    if not ids:
        messages.warning(request, "Aucune commande sélectionnée.")
        return redirect('mise_a_jour_statuts_livraisons')

    commandes = Commande.objects.filter(id__in=ids)

    # ---------------------------
    # Cas simples : Annulée / Livrée
    # ---------------------------
    if action == 'annulée':
        # Bloquer si une des commandes est déjà payée
        deja_payees = list(
            commandes.filter(statut_vente='Payée').values_list('numero_facture', flat=True)
        )
        if deja_payees:
            factures = ", ".join(deja_payees)
            messages.warning(
                request,
                (
                    "Vente déjà payée pour "
                    f"{factures} ; reportez la livraison ou supprimez d'abord l'encaissement de la vente."
                )
            )
            return redirect('mise_a_jour_statuts_livraisons')

        # Sinon, on annule livraison ET vente
        updated = commandes.update(statut_livraison='Annulée', statut_vente='Annulée')
        messages.success(request, f"{updated} commande(s) annulée(s) avec succès.")
        return redirect('mise_a_jour_statuts_livraisons')

    if action == 'livrée':
        # On ne touche PAS à statut_vente
        updated = commandes.update(statut_livraison='Livrée')
        messages.success(request, f"{updated} commande(s) livrée(s) avec succès.")
        return redirect('mise_a_jour_statuts_livraisons')

    # ---------------------------
    # Cas particulier : Reportée
    # ---------------------------
    if action == 'reportée':
        if not nouvelle_date:
            messages.warning(request, "Veuillez spécifier une nouvelle date de livraison.")
            return redirect('mise_a_jour_statuts_livraisons')

        try:
            nouvelle_date_obj = datetime.strptime(nouvelle_date, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Format de date invalide (attendu AAAA-MM-JJ).")
            return redirect('mise_a_jour_statuts_livraisons')

        date_formatee = nouvelle_date_obj.strftime("%d/%m/%Y")

        with transaction.atomic():
            qs = (
                commandes.select_related('client', 'page')
                .prefetch_related('lignes_commandes')
            )

            for commande in qs:
                statut_vente_initial = commande.statut_vente
                remarque_initiale = (commande.remarque or "").strip()

                prefix = f"Reportée au {date_formatee}"
                if not remarque_initiale.startswith(prefix):
                    nouvelle_remarque_existante = f"{prefix}\n{remarque_initiale}".strip()
                else:
                    nouvelle_remarque_existante = remarque_initiale

                commande.statut_livraison = 'Reportée'
                commande.remarque = nouvelle_remarque_existante
                commande.save()

                nouvelle_commande = Commande.objects.create(
                    client=commande.client,
                    page=commande.page,
                    remarque=remarque_initiale,         # pas de "Reportée..." copié
                    statut_vente=statut_vente_initial,  # on conserve
                    statut_livraison='En attente',
                    frais_livraison=commande.frais_livraison,
                    date_livraison=nouvelle_date_obj,
                    livreur=None,
                    frais_livreur=commande.frais_livreur,
                    paiement_frais_livreur='Non payée'
                )

                lignes = [
                    LigneCommande(
                        commande=nouvelle_commande,
                        article=ligne.article,
                        prix_unitaire=ligne.prix_unitaire,
                        prix_achat=ligne.prix_achat,
                        quantite=ligne.quantite,
                    )
                    for ligne in commande.lignes_commandes.all()
                ]
                LigneCommande.objects.bulk_create(lignes)

        messages.success(
            request,
            f"{commandes.count()} commande(s) reportée(s) au {nouvelle_date_obj.strftime('%Y-%m-%d')}."
        )
        return redirect('mise_a_jour_statuts_livraisons')

    # ---------------------------
    # Action inconnue
    # ---------------------------
    messages.error(request, "Action non reconnue.")
    return redirect('mise_a_jour_statuts_livraisons')

@login_required
def liste_livreurs(request):
    livreurs = Livreur.objects.all()
    form = LivreurForm()
    return render(request, 'livraison/liste_livreurs.html', {'livreurs': livreurs, 'form': form})

@login_required
@admin_required
def ajouter_livreur(request):
    if request.method == 'POST':
        form = LivreurForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect('liste_livreurs')

@login_required
@admin_required
def modifier_livreur(request, id):
    livreur = get_object_or_404(Livreur, id=id)
    if request.method == 'POST':
        form = LivreurForm(request.POST, instance=livreur)
        if form.is_valid():
            form.save()
    return redirect('liste_livreurs')

@login_required
@admin_required
def supprimer_livreur(request, id):
    livreur = get_object_or_404(Livreur, id=id)
    livreur.soft_delete(user=request.user)
    messages.success(request, f"Le livreur « {livreur.nom} » a été supprimé (soft delete).")
    return redirect('liste_livreurs')

@login_required
@admin_required
@require_POST
def restaurer_livreur(request, id):
    """Restore (avec mot de passe, POST only)."""
    if not _check_password(request):
        messages.warning(request, "Mot de passe incorrect. Restauration annulée.")
        return redirect('liste_livreurs')

    livreur = get_object_or_404(Livreur, id=id)
    livreur.restore(user=request.user)
    messages.success(request, f"Le livreur « {livreur.nom} » a été restauré avec succès.")
    return redirect('liste_livreurs')

@login_required
def frais_livraison_list(request):
    lieu_recherche = request.GET.get('lieu', '').strip()
    categorie_filtre = request.GET.get('categorie', '')

    frais_livraisons = Livraison.objects.all()

    if lieu_recherche:
        frais_livraisons = frais_livraisons.filter(lieu__icontains=lieu_recherche)
    if categorie_filtre:
        frais_livraisons = frais_livraisons.filter(categorie=categorie_filtre)

    frais_livraisons = frais_livraisons.order_by('lieu')

    # Pagination
    paginator = Paginator(frais_livraisons, 40)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Extra querystring propre (sans page)
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != 'page':
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    return render(request, 'livraison/frais_livraison.html', {
        'page_obj': page_obj,
        'categories': CATEGORIE_CHOIX,
        'lieu_recherche': lieu_recherche,
        'categorie_filtre': categorie_filtre,
        'extra_querystring': extra_querystring,
        'is_admin': is_admin(request.user),
        'FRAIS_LIVRAISON_PAR_DEFAUT': FRAIS_LIVRAISON_PAR_DEFAUT,
        'FRAIS_LIVREUR_PAR_DEFAUT': FRAIS_LIVREUR_PAR_DEFAUT,
    })

@login_required
@require_POST
def frais_livraison_ajouter(request):
    lieu = request.POST.get('lieu', '').strip()
    categorie = request.POST.get('categorie', '').strip()
    frais_livraison = request.POST.get('frais_livraison', '').strip()
    frais_livreur = request.POST.get('frais_livreur', '').strip()

    if not lieu or not categorie:
        return JsonResponse({'error': 'Champs obligatoires manquants.'}, status=400)

    try:
        frais_livraison = int(frais_livraison) if frais_livraison else FRAIS_LIVRAISON_PAR_DEFAUT.get(categorie, 0)
    except (TypeError, ValueError):
        frais_livraison = FRAIS_LIVRAISON_PAR_DEFAUT.get(categorie, 0)

    try:
        frais_livreur = int(frais_livreur) if frais_livreur else FRAIS_LIVREUR_PAR_DEFAUT.get(categorie, 0)
    except (TypeError, ValueError):
        frais_livreur = FRAIS_LIVREUR_PAR_DEFAUT.get(categorie, 0)

    Livraison.objects.create(
        lieu=lieu,
        categorie=categorie,
        frais_livraison=frais_livraison,
        frais_livreur=frais_livreur
    )
    return redirect('frais_livraison_list')

@login_required
@require_POST
def frais_livraison_modifier(request, id):
    frais = get_object_or_404(Livraison, id=id)

    lieu = request.POST.get('lieu', '').strip()
    categorie = request.POST.get('categorie', '').strip()
    frais_livraison = request.POST.get('frais_livraison', '').strip()
    frais_livreur = request.POST.get('frais_livreur', '').strip()

    if not lieu or not categorie:
        return JsonResponse({'error': 'Champs obligatoires manquants.'}, status=400)

    frais.lieu = lieu
    frais.categorie = categorie

    try:
        frais.frais_livraison = int(frais_livraison) if frais_livraison else FRAIS_LIVRAISON_PAR_DEFAUT.get(categorie, 0)
    except (TypeError, ValueError):
        frais.frais_livraison = FRAIS_LIVRAISON_PAR_DEFAUT.get(categorie, 0)

    try:
        frais.frais_livreur = int(frais_livreur) if frais_livreur else FRAIS_LIVREUR_PAR_DEFAUT.get(categorie, 0)
    except (TypeError, ValueError):
        frais.frais_livreur = FRAIS_LIVREUR_PAR_DEFAUT.get(categorie, 0)

    frais.save()
    return redirect('frais_livraison_list')

@login_required
@admin_required
def frais_livraison_supprimer(request, id):
    frais = get_object_or_404(Livraison, id=id)
    frais.soft_delete(user=request.user)
    return redirect('frais_livraison_list')


@login_required
@admin_required
def paiement_frais_livraisons(request):
    livreurs = Livreur.objects.all()
    commandes = Commande.objects.order_by('-date_livraison')

    livreur_id = request.GET.get('livreur')
    selected_date = request.GET.get('date')
    selected_statut = request.GET.get('statut_livraison')
    selected_paiement_frais = request.GET.get('paiement_frais')

    # ✅ Redirection si les filtres par défaut doivent être forcés
    if request.GET.get("page") is None and selected_paiement_frais is None:
        query_params = request.GET.copy()
        query_params["paiement_frais"] = "Non payée"
        if "statut_livraison" not in query_params:
            query_params["statut_livraison"] = "Livrée"
        return redirect(f"{request.path}?{query_params.urlencode()}")

    # Filtres
    if livreur_id:
        commandes = commandes.filter(livreur_id=livreur_id)
    if selected_date:
        from django.utils.dateparse import parse_date
        date_parsed = parse_date(selected_date)
        if date_parsed:
            commandes = commandes.filter(date_livraison=date_parsed)
    if selected_statut:
        commandes = commandes.filter(statut_livraison=selected_statut)
    if selected_paiement_frais:
        commandes = commandes.filter(paiement_frais_livreur=selected_paiement_frais)

    # 🔢 Total des frais pour la sélection
    total_frais = sum(
        (c.frais_livreur or 0) for c in commandes
    )

    # Pagination
    paginator = Paginator(commandes, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Querystring propre
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != 'page':
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    return render(request, 'livraison/paiement_frais_livraisons.html', {
        'commandes': page_obj.object_list,
        'page_obj': page_obj,
        'livreurs': livreurs,
        'lieux': Livraison.objects.order_by('lieu'),
        'selected_livreur': livreur_id,
        'selected_date': selected_date,
        'selected_statut': selected_statut,
        'selected_paiement_frais': selected_paiement_frais,
        'total_frais': total_frais,
        'extra_querystring': extra_querystring,
        'is_admin': is_admin(request.user),
        'caisses': Caisse.objects.all(),
        'today': now().date(),
    })

@login_required
@admin_required
def paiement_frais_livraisons_groupes(request):
    if request.method == 'POST':
        commande_ids = set(request.POST.getlist('commandes'))
        paiement_id = request.POST.get('paiement')
        date_paiement = request.POST.get('date_paiement')

        if not commande_ids or not paiement_id or not date_paiement:
            messages.error(request, "Tous les champs sont requis pour enregistrer un paiement.")
            return redirect('paiement_frais_livraisons')

        caisse = get_object_or_404(Caisse, pk=paiement_id)
        compte_charge = get_object_or_404(PlanDesComptes, pk=10)  # Service de livraison (Frais livreur)
        created_count = 0

        for cid in commande_ids:
            try:
                commande = Commande.objects.get(pk=cid)
                pu = commande.frais_livreur or 0
                if pu <= 0:
                    continue

                Charge.objects.create(
                    date=date_paiement,
                    libelle=compte_charge,
                    pu=pu,
                    quantite=1,
                    montant=pu,
                    remarque=f"{commande.livreur.nom} ({commande.numero_facture})" if commande.livreur else '',
                    paiement=caisse,
                    page=commande.page
                )

                commande.paiement_frais_livreur = "Payée"
                commande.save()
                created_count += 1
            except Commande.DoesNotExist:
                continue

        messages.success(request, f"{created_count} charge(s) enregistrée(s) avec succès.")
        return redirect('paiement_frais_livraisons')

    return redirect('paiement_frais_livraisons')

@login_required
def modifier_frais_livraisons(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)
    if request.method == 'POST':
        livreur_id = request.POST.get('livreur')
        frais = request.POST.get('frais_livreur')

        if livreur_id and frais:
            commande.livreur_id = livreur_id
            commande.frais_livreur = int(frais)
            commande.save()
            messages.success(request, "Livraison mise à jour avec succès.")
        else:
            messages.error(request, "Veuillez remplir tous les champs.")
    return redirect('paiement_frais_livraisons')