# clients/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.contrib import messages 
from django.core.validators import validate_email, URLValidator
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import QueryDict
from common.decorators import admin_required
from common.utils import is_admin, resolve_display_mode
from livraison.models import Livraison
from .models import Client, Entreprise

def _build_clients_context(request):
    nom = request.GET.get("nom", "").strip()
    lieu = request.GET.get("lieu", "").strip()
    contact = request.GET.get("contact", "").strip()

    qs = Client.objects.all()

    if nom:
        qs = qs.filter(nom__icontains=nom)
    if lieu:
        qs = qs.filter(lieu__lieu__icontains=lieu)
    if contact:
        qs = qs.filter(contact__icontains=contact)

    qs = qs.order_by("nom")

    # Pagination
    paginator = Paginator(qs, 24)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # QS propre (sans page vide)
    params = request.GET.copy()
    clean = QueryDict(mutable=True)
    for k, values in params.lists():
        vclean = [v for v in values if v.strip()]
        if vclean and k != "page":
            clean.setlist(k, vclean)
    extra_querystring = "&" + clean.urlencode() if clean else ""

    display_mode = resolve_display_mode(request, session_key="display_clients", default="cards")

    return {
        "clients": page_obj.object_list,
        "lieux": Livraison.objects.all().order_by("lieu"),
        "nom_query": nom,               
        "lieu_query": lieu,
        "contact_query": contact,
        "is_admin": is_admin(request.user),
        "page_obj": page_obj,
        "extra_querystring": extra_querystring,
        "display_mode": display_mode,
    }

@login_required
def clients_list(request):
    ctx = _build_clients_context(request)
    return render(request, "clients/clients_list.html", ctx)

@login_required
def clients_list_partial(request):
    ctx = _build_clients_context(request)
    # Si appel direct sans HTMX → page complète
    if request.headers.get("HX-Request") != "true":
        return render(request, "clients/clients_list.html", ctx)
    return render(request, "clients/includes/clients_list_wrapper.html", ctx)

@login_required
@require_POST
def client_create(request):
    nom = request.POST.get("nom")
    lieu_id = request.POST.get("lieu")
    precision_lieu = request.POST.get("precision_lieu", "")
    contact = request.POST.get("contact")
    reference_client = request.POST.get("reference_client")

    if nom and lieu_id and contact:
        lieu_obj = get_object_or_404(Livraison, id=lieu_id)
        Client.objects.create(
            nom=nom,
            lieu=lieu_obj,
            precision_lieu=precision_lieu,
            contact=contact,
            reference_client=reference_client
        )
    return redirect("clients_list")

@login_required
@require_POST
def client_update(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if client.statut_publication == "supprimé":
        messages.warning(request, "Ce client a été supprimé et ne peut être modifié.")
        return redirect("clients_list")

    client.nom = request.POST.get("nom")
    lieu_id = request.POST.get("lieu")
    client.lieu = get_object_or_404(Livraison, id=lieu_id)
    client.precision_lieu = request.POST.get("precision_lieu", "")
    client.contact = request.POST.get("contact")
    client.reference_client = request.POST.get("reference_client")
    client.save()
    return redirect("clients_list")

@login_required
@admin_required
@require_POST
def client_delete(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if client.statut_publication == "supprimé":
        messages.warning(request, "Ce client a déjà été supprimée.")
        return redirect("clients_list")

    # client.delete()
    client.soft_delete(user=request.user)
    return redirect("clients_list")

@login_required
def entreprises_list(request):
    raison_sociale_query = request.GET.get("raison_sociale", "").strip()
    activite_query = request.GET.get("activite", "").strip()
    contact_query = request.GET.get("contact", "").strip()

    entreprises_qs = Entreprise.objects.all()

    if raison_sociale_query:
        entreprises_qs = entreprises_qs.filter(raison_sociale__icontains=raison_sociale_query)
    if activite_query:
        entreprises_qs = entreprises_qs.filter(activite_produits__icontains=activite_query)
    if contact_query:
        entreprises_qs = entreprises_qs.filter(telephone__icontains=contact_query)

    entreprises_qs = entreprises_qs.order_by('raison_sociale')

    paginator = Paginator(entreprises_qs, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        clean_values = [v for v in values if v.strip()]
        if clean_values and key != "page":
            clean_params.setlist(key, clean_values)
    extra_querystring = "&" + clean_params.urlencode() if clean_params else ""

    return render(request, "clients/entreprises_list.html", {
        "entreprises": page_obj.object_list,
        "raison_sociale_query": raison_sociale_query,
        "activite_query": activite_query,
        "contact_query": contact_query,
        "is_admin": is_admin(request.user),
        "page_obj": page_obj,
        "extra_querystring": extra_querystring,
    })

@login_required
@require_POST
def entreprise_create(request):
    # Récupération des champs
    data = {k: request.POST.get(k) or None for k in [
        "raison_sociale", "date_debut", "page_facebook", "lien_page",
        "activite_produits", "personne_de_contact", "lien_profil",
        "nif", "stat", "rcs", "adresse", "telephone", "email",
        "fokontany", "commune", "region", "cin_numero", "date_cin",
        "lieu_cin", "remarque"
    ]}

    # Parsing des dates
    data["date_debut"] = parse_date(data["date_debut"]) if data["date_debut"] else None
    data["date_cin"]   = parse_date(data["date_cin"])   if data["date_cin"]   else None

    # Validation minimale côté serveur
    errors = []
    if not data["raison_sociale"]:
        errors.append("La raison sociale est obligatoire.")

    # Validations optionnelles
    url_validator = URLValidator()
    for field in ["lien_page", "lien_profil"]:
        if data[field]:
            try:
                url_validator(data[field])
            except ValidationError:
                errors.append(f"L’URL fournie pour « {field.replace('_', ' ')} » est invalide.")

    if data["email"]:
        try:
            validate_email(data["email"])
        except ValidationError:
            errors.append("L’email fourni est invalide.")

    if errors:
        for e in errors:
            messages.warning(request, e)
        # Astuce : on renvoie un flag pour rouvrir le modal d’ajout côté client
        return redirect(f"{request.META.get('HTTP_REFERER','/')}?open=addEntrepriseModal")

    # Création en transaction
    try:
        with transaction.atomic():
            Entreprise.objects.create(**data)
            messages.success(request, "Entreprise ajoutée avec succès.")
    except IntegrityError as e:
        messages.warning(request, f"Erreur lors de l’enregistrement : {e}")

    return redirect("entreprises_list")


@login_required
@require_POST
def entreprise_update(request, entreprise_id):
    entreprise = get_object_or_404(Entreprise, id=entreprise_id)

    # Récupération & normalisation
    data = {k: request.POST.get(k) or None for k in [
        "raison_sociale", "date_debut", "page_facebook", "lien_page",
        "activite_produits", "personne_de_contact", "lien_profil",
        "nif", "stat", "rcs", "adresse", "telephone", "email",
        "fokontany", "commune", "region", "cin_numero", "date_cin",
        "lieu_cin", "remarque"
    ]}
    data["date_debut"] = parse_date(data["date_debut"]) if data["date_debut"] else None
    data["date_cin"]   = parse_date(data["date_cin"])   if data["date_cin"]   else None

    errors = []
    if not data["raison_sociale"]:
        errors.append("La raison sociale est obligatoire.")

    url_validator = URLValidator()
    for field in ["lien_page", "lien_profil"]:
        if data[field]:
            try:
                url_validator(data[field])
            except ValidationError:
                errors.append(f"L’URL fournie pour « {field.replace('_', ' ')} » est invalide.")

    if data["email"]:
        try:
            validate_email(data["email"])
        except ValidationError:
            errors.append("L’email fourni est invalide.")

    if errors:
        for e in errors:
            messages.warning(request, e)
        return redirect(f"{request.META.get('HTTP_REFERER','/')}?open=editModal{entreprise.id}")

    # Affectation et sauvegarde
    for field, val in data.items():
        setattr(entreprise, field, val)

    try:
        with transaction.atomic():
            entreprise.save()
            messages.success(request, "Entreprise mise à jour avec succès.")
    except IntegrityError as e:
        messages.warning(request, f"Erreur lors de la mise à jour : {e}")

    return redirect("entreprises_list")

@login_required
@admin_required
@require_POST
def entreprise_delete(request, entreprise_id):
    entreprise = get_object_or_404(Entreprise, id=entreprise_id)

    if hasattr(entreprise, "soft_delete"):
        entreprise.soft_delete(user=request.user)
    else:
        entreprise.delete()

    return redirect("entreprises_list")
