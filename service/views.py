from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, QueryDict
from django.contrib import messages
from django.db.models import Sum
from django.core.paginator import Paginator
from django.utils.timezone import now
from django.utils.dateparse import parse_date
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_http_methods
from django.db import IntegrityError, transaction
from django.contrib.auth.decorators import login_required
from common.decorators import admin_required
from common.utils import is_admin
from common.pdf import render_html_to_pdf, render_single_page_pdf
from urllib.parse import urlencode

from datetime import date
import json
from django.core.serializers.json import DjangoJSONEncoder

from .models import Commande, LigneCommande, Vente
from clients.models import Entreprise
from articles.models import Service
from common.models import Pages, Caisse

@login_required
def liste_commandes_services(request):
    qs = (Commande.objects
          .select_related('client', 'page')
          .prefetch_related('lignes_commandes__service')
          .order_by('-date_commande'))

    # ---- Lire & nettoyer les filtres ----
    filtre_date_commande = (request.GET.get('date_commande') or "").strip()
    filtre_service_id_raw = (request.GET.get('service_id') or "").strip()
    filtre_client_id_raw = (request.GET.get('client_id') or "").strip()
    filtre_statut = (request.GET.get('statut') or "").strip()
    page_id = (request.GET.get('page_id') or "").strip()

    # caster au besoin
    def parse_int(s):
        try:
            return int(s)
        except (TypeError, ValueError):
            return None

    filtre_service_id = parse_int(filtre_service_id_raw)
    filtre_client_id = parse_int(filtre_client_id_raw)

    # ---- Appliquer les filtres ----
    if filtre_statut:
        qs = qs.filter(statut_vente=filtre_statut)
    if page_id:
        qs = qs.filter(page_id=page_id)
    if filtre_date_commande:
        qs = qs.filter(date_commande=filtre_date_commande)
    if filtre_client_id:
        qs = qs.filter(client_id=filtre_client_id)
    if filtre_service_id:
        qs = qs.filter(lignes_commandes__service_id=filtre_service_id).distinct()

    commandes_valides = qs.exclude(statut_vente__in=["Annulée", "Supprimée"])
    total_montant = sum(c.montant_commande for c in commandes_valides)

    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # conserver les filtres dans la pagination
    extra_querystring = urlencode({
        'date_commande': filtre_date_commande,
        'service_id': filtre_service_id_raw,
        'client_id': filtre_client_id_raw,
        'statut': filtre_statut,
        'page_id': page_id,
    })

    context = {
        'commandes': page_obj.object_list,
        'page_obj': page_obj,

        'filtre_date_commande': filtre_date_commande,
        'filtre_service_id': filtre_service_id_raw,  # garder la raw string pour l’affichage
        'filtre_client_id': filtre_client_id_raw,
        'filtre_statut': filtre_statut,
        'filtre_page': page_id,

        'pages': Pages.actifs.filter(type="SERVICE"),
        'services': Service.actifs.all(),
        'clients': Entreprise.actifs.all().order_by('raison_sociale'),

        'total_montant': total_montant,
        'extra_querystring': extra_querystring,
    }
    return render(request, 'service/liste_commandes_services.html', context)

@login_required
def detail_commande_service(request, commande_id):
    commande = get_object_or_404(Commande.objects.select_related('client', 'page'), id=commande_id)
    lignes = commande.lignes_commandes.select_related('service').all()

    context = {
        'commande': commande,
        'lignes': lignes,
        'montant_commande': commande.montant_commande,
    }
    return render(request, 'service/detail_commande_service.html', context)

@login_required
def detail_commande_service_modal(request, commande_id):
    commande = get_object_or_404(
        Commande.objects.select_related('client', 'page'),
        id=commande_id
    )
    lignes = commande.lignes_commandes.select_related('service').all()

    html = render_to_string(
        'service/includes/commande_service_detail_modal.html',
        {
            'commande': commande,
            'lignes': lignes,
            'montant_commande': commande.montant_commande,
        },
        request=request
    )
    return JsonResponse({'html': html})

@login_required
def creer_commande_service(request):
    pages = Pages.actifs.filter(type="SERVICE")
    services = Service.actifs.all()

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Entreprise, id=client_id)

        page_id = request.POST.get('page')
        page = get_object_or_404(Pages, id=page_id)

        commande = Commande.objects.create(
            client=client,
            page=page,
            remarque=request.POST.get('remarque'),
            date_commande=request.POST.get('date_commande') or now(),
        )

        service_ids = request.POST.getlist('service')
        tarifs = request.POST.getlist('tarif')
        quantites = request.POST.getlist('quantite')

        for i in range(len(service_ids)):
            service = get_object_or_404(Service, pk=service_ids[i])
            tarif = int(tarifs[i])
            quantite = int(quantites[i])
            LigneCommande.objects.create(
                commande=commande,
                service=service,
                tarif=tarif,
                quantite=quantite
            )

        return redirect('detail_commande_service', commande_id=commande.id)
    
    services_json = json.dumps(
        list(services.values("id", "nom", "reference", "tarif")),
        cls=DjangoJSONEncoder
    )
    
    return render(request, 'service/creer_commande_service.html', {
        'pages': pages,
        'services': services,
        'clients' : Entreprise.actifs.all().order_by('raison_sociale'),
        'date_du_jour': now().date(),
        'services_json': services_json,
    })

@login_required
def modifier_commande_service(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)

    if commande.actions_desactivees():
        messages.warning(request, "Modification interdite pour cette commande.")
        return redirect('detail_commande_service', commande_id=commande.id)

    pages = Pages.actifs.filter(type="SERVICE")
    services = Service.actifs.all()

    if request.method == 'POST':
        commande.page = get_object_or_404(Pages, id=request.POST.get('page'))
        commande.remarque = request.POST.get('remarque')
        commande.date_commande = request.POST.get('date_commande') or now()
        commande.save()

        LigneCommande.objects.filter(commande=commande).delete()

        service_ids = request.POST.getlist('service')
        tarifs = request.POST.getlist('tarif')
        quantites = request.POST.getlist('quantite')

        for i in range(len(service_ids)):
            service = get_object_or_404(Service, pk=service_ids[i])
            tarif = int(tarifs[i])
            quantite = int(quantites[i])
            LigneCommande.objects.create(
                commande=commande,
                service=service,
                tarif=tarif,
                quantite=quantite
            )

        return redirect('detail_commande_service', commande_id=commande.id)

    lignes = commande.lignes_commandes.all()

    return render(request, 'service/modifier_commande_service.html', {
        'commande': commande,
        'pages': pages,
        'services': services,
        'lignes': lignes,
    })

@login_required
def supprimer_commande_service(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)

    if commande.actions_desactivees():
        messages.warning(request, "Impossible de supprimer cette commande.")
        return redirect('liste_commandes_services')

    if request.method == 'POST':
        commande.statut_vente = "Supprimée"
        commande.save(update_fields=["statut_vente"])
        commande.soft_delete(user=request.user)
        messages.success(request, "Commande supprimée avec succès.")
        return redirect('liste_commandes_services')

    return redirect('liste_commandes_services')

@login_required
def encaissement_services(request):
    """
    Liste des commandes de service, avec encaissement unitaire.
    Par défaut : seulement 'En attente'.
    """
    selected_date = request.GET.get("date_commande")
    selected_statut_vente = request.GET.get("statut_vente") or "En attente"

    commandes = (Commande.objects
                 .select_related("client", "page")
                 .prefetch_related("lignes_commandes__service")
                 .order_by("date_commande"))

    # Par défaut : uniquement en attente
    if not request.GET:
        commandes = commandes.filter(statut_vente="En attente")
    else:
        if selected_statut_vente:
            commandes = commandes.filter(statut_vente=selected_statut_vente)
        if selected_date:
            commandes = commandes.filter(date_commande=selected_date)

    total_montant = sum(c.montant_commande for c in commandes)

    paginator = Paginator(commandes, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != "page":
            clean_params.setlist(key, clean_values)
    extra_querystring = "&" + clean_params.urlencode() if clean_params else ""

    caisses = Caisse.actifs.all()
    today = now().date()

    context = {
        "commandes": page_obj.object_list,
        "page_obj": page_obj,
        "extra_querystring": extra_querystring,
        "caisses": caisses,
        "today": today,
        "selected_date": selected_date or "",
        "selected_statut_vente": selected_statut_vente or "",
        "total_montant": total_montant,
        "is_admin": request.user.is_staff,  # si utile pour le bouton
    }
    return render(request, "service/encaissement_services.html", context)

from django.db import transaction
from django.db.models import Exists, OuterRef

@login_required
def encaissement_service_unitaire(request):
    if request.method != "POST":
        messages.warning(request, "Méthode non autorisée.")
        return redirect("encaissement_services")

    commande_id = request.POST.get("commande_id")
    paiement_id = request.POST.get("paiement")
    date_encaissement_str = request.POST.get("date_encaissement")
    date_encaissement = parse_date(date_encaissement_str) or now().date()
    reference = (request.POST.get("reference") or "").strip()

    if not commande_id:
        messages.warning(request, "Commande manquante.")
        return redirect("encaissement_services")

    if not paiement_id:
        messages.warning(request, "Veuillez choisir un mode de paiement.")
        return redirect("encaissement_services")

    try:
        with transaction.atomic():
            # Verrouille la commande pendant l’opération
            commande = (Commande.objects
                        .select_for_update()
                        .annotate(a_deja_vente=Exists(
                            Vente.objects.filter(commande_id=OuterRef("pk"))
                        ))
                        .get(pk=commande_id))

            paiement = Caisse.actifs.select_for_update().get(pk=paiement_id)

            # Garde-fous
            if commande.statut_vente in ("Payée", "Supprimée"):
                messages.warning(
                    request,
                    f"La commande {commande.numero_proforma} n'est pas encaisseable (statut : {commande.statut_vente})."
                )
                raise transaction.Rollback  # stoppe proprement

            if commande.a_deja_vente:
                messages.warning(
                    request,
                    f"La commande {commande.numero_proforma} est déjà encaissée."
                )
                raise transaction.Rollback

            # Création de la vente
            vente = Vente.objects.create(
                commande=commande,
                paiement=paiement,
                montant=commande.montant_commande,
                date_encaissement=date_encaissement,
                reference=reference or None,
            )

            # Mise à jour du statut
            commande.statut_vente = "Payée"
            commande.save(update_fields=["statut_vente"])

    except Commande.DoesNotExist:
        messages.error(request, "Commande introuvable.")
    except Caisse.DoesNotExist:
        messages.error(request, "Caisse invalide ou inactive.")
    except transaction.Rollback:
        # messages déjà posés
        pass
    except Exception as e:
        messages.error(request, f"Erreur lors de l'encaissement : {e}")
    else:
        messages.success(
            request,
            f"Commande {commande.numero_proforma} encaissée avec succès. "
            f"Facture générée : {vente.numero_facture}."
        )

    return redirect("encaissement_services")


STATUTS_VENTE = ["En attente", "Payée", "Supprimée"]

@login_required
def facturation_commandes_services(request):
    """
    Liste filtrable/paginée des commandes de service à facturer (ou déjà facturées).
    Par défaut on affiche les 'Payée' pour impression de facture.
    """
    params = request.GET.copy()
    selected_date = params.get("date_commande")
    selected_statut = params.get("statut_vente")

    type_facture = params.get("type_facture")  # peut être None ici; l'UI mettra la valeur par défaut

    # Premier chargement : afficher tous les statuts
    is_initial_load = not request.GET
    if is_initial_load:
        selected_statut = ""

    commandes = Commande.objects.all().order_by('-date_commande', '-numero_proforma')

    # Filtres
    if selected_date:
        parsed_date = parse_date(selected_date)
        if parsed_date:
            commandes = commandes.filter(date_commande=parsed_date)

    if selected_statut:
        commandes = commandes.filter(statut_vente=selected_statut)

    # Pagination
    paginator = Paginator(commandes, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Conserver les filtres dans la pagination (hors 'page')
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        if key != 'page':
            clean_values = [v for v in values if v.strip() or v == '']
            clean_params.setlist(key, clean_values)
    extra_querystring = '&' + clean_params.urlencode() if clean_params else ''

    context = {
        "commandes": page_obj.object_list,
        "page_obj": page_obj,
        "selected_date": selected_date or "",
        "selected_statut": selected_statut or "",
        "extra_querystring": extra_querystring,
        "statuts_vente": STATUTS_VENTE,
        "type_facture": type_facture,
    }
    return render(request, "service/facturation_commandes_services.html", context)


@login_required
def facturation_commandes_services_partial(request):
    """
    Partial pour recharger uniquement le tableau (HTMX/Ajax).
    """
    response = facturation_commandes_services(request)
    response.template_name = 'service/includes/facturation_services_table.html'
    return response

def _default_type_for_commande(commande):
    return "FACTURE" if commande.statut_vente == "Payée" else "FACTURE PROFORMA"


@login_required
@require_http_methods(["POST"])
def voir_factures_services(request):
    commande_id = request.POST.get("commande_id")
    if not commande_id:
        messages.error(request, "Veuillez sélectionner une commande.")
        return redirect('facturation_commandes_services')

    commande = get_object_or_404(Commande, id=commande_id)
    requested_type = request.POST.get("type_facture")
    effective_type = requested_type or _default_type_for_commande(commande)

    # FACTURE interdit si non Payée
    if effective_type == "FACTURE" and commande.statut_vente != "Payée":
        messages.error(request, "Type FACTURE non autorisé : la commande sélectionnée n'est pas Payée.")
        return redirect('facturation_commandes_services')

    caisses = Caisse.objects.all()

    return render(request, "service/factures_services.html", {
        "commandes": Commande.objects.filter(id=commande.id),
        "impression": False,
        "type_facture": effective_type,
        "caisses": caisses,   
    })


@login_required
def imprimer_factures_services(request):
    if request.method != 'POST':
        return redirect('facturation_commandes_services')

    commande_id = request.POST.get('commande_id')
    if not commande_id:
        messages.error(request, "Veuillez sélectionner une commande.")
        return redirect('facturation_commandes_services')

    commande = get_object_or_404(Commande, id=commande_id)
    requested_type = request.POST.get("type_facture")
    effective_type = requested_type or _default_type_for_commande(commande)

    if effective_type == "FACTURE" and commande.statut_vente != "Payée":
        messages.error(request, "Type FACTURE non autorisé : la commande sélectionnée n'est pas Payée.")
        return redirect('facturation_commandes_services')

    caisses = Caisse.objects.all()

    return render(request, 'service/factures_services.html', {
        'commandes': Commande.objects.filter(id=commande.id),
        'impression': True,
        'type_facture': effective_type,
        'caisses': caisses,  
    })

@login_required
@require_http_methods(["POST"])
def telecharger_facture_service_pdf(request):
    """
    Génère un PDF de la facture/proforma pour la commande sélectionnée.
    """
    commande_id = request.POST.get("commande_id")
    if not commande_id:
        messages.error(request, "Veuillez sélectionner une commande.")
        return redirect('facturation_commandes_services')

    commande = get_object_or_404(Commande, id=commande_id)

    # Type demandé ou défaut (FACTURE si Payée sinon PROFORMA)
    requested_type = request.POST.get("type_facture")
    effective_type = requested_type or ("FACTURE" if commande.statut_vente == "Payée" else "FACTURE PROFORMA")

    # FACTURE interdit si non Payée
    if effective_type == "FACTURE" and commande.statut_vente != "Payée":
        messages.error(request, "Type FACTURE non autorisé : la commande sélectionnée n'est pas Payée.")
        return redirect('facturation_commandes_services')

    caisses = Caisse.objects.all()

    context = {
        "commandes": Commande.objects.filter(id=commande.id),
        "impression": False,     # inutile ici, on rend en PDF
        "type_facture": effective_type,
        "caisses": caisses,
    }

    # filename = f"{'FACTURE' if effective_type=='FACTURE' else 'PROFORMA'}_{commande.numero_proforma or commande.id}.pdf"
    # return render_html_to_pdf("service/factures_services.html", context, request, filename)
    return render_html_to_pdf("service/factures_services.html", context, request,
        filename=f"{effective_type}_{commande.numero_proforma or commande.id}.pdf")
