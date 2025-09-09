# charges/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate
from django.contrib import messages 
from django.core.paginator import Paginator
from django.http import QueryDict
from datetime import date
from django.db.models import Sum
from common.decorators import admin_required
from common.utils import is_admin, resolve_display_mode
from .models import Charge
from common.models import PlanDesComptes, Caisse, Pages

def _build_charges_context(request):
    charges_qs = Charge.objects.select_related("libelle", "paiement", "page") \
                               .all().order_by("-date", "remarque")

    # Filtres
    date_filter = request.GET.get("date_filter", "")
    libelle = request.GET.get("libelle", "").strip()
    paiement = request.GET.get("paiement", "")
    page_filter = request.GET.get("page_filter", "")

    if date_filter:
        charges_qs = charges_qs.filter(date=date_filter)
    if libelle:
        charges_qs = charges_qs.filter(libelle__libelle__icontains=libelle)
    if paiement:
        charges_qs = charges_qs.filter(paiement__id=paiement)
    if page_filter:
        if page_filter == "none":
            charges_qs = charges_qs.filter(page__isnull=True)
        else:
            charges_qs = charges_qs.filter(page__id=page_filter)

    # Total sur charges publiées (et filtrées)
    total_charges = charges_qs.filter(
        statut_publication="publié",
        libelle__compte_numero__startswith='6'
    ).aggregate(Sum('montant'))['montant__sum'] or 0

    # Pagination
    paginator = Paginator(charges_qs, 24)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # QS propre (sans page vide)
    params = request.GET.copy()
    clean_params = QueryDict(mutable=True)
    for key, values in params.lists():
        vclean = [v for v in values if v.strip()]
        if vclean and key != "page":
            clean_params.setlist(key, vclean)
    extra_querystring = "&" + clean_params.urlencode() if clean_params else ""

    display_mode = resolve_display_mode(request, session_key="display_charges", default="cards")

    return {
        "charges": page_obj.object_list,
        "total_charges": total_charges,
        "plans": PlanDesComptes.objects.all().order_by('compte_numero'),
        "caisses": Caisse.objects.all(),
        "pages": Pages.objects.all(),
        "today": date.today().isoformat(),
        "is_admin": is_admin(request.user),
        "filters": {
            "date_filter": date_filter,
            "libelle": libelle,
            "paiement": paiement,
            "page_filter": page_filter,
        },
        "page_obj": page_obj,
        "extra_querystring": extra_querystring,
        "display_mode": display_mode,
    }

@login_required
@admin_required
def charges_list(request):
    ctx = _build_charges_context(request)
    return render(request, "charges/charges_list.html", ctx)

@login_required
def charges_list_partial(request):
    ctx = _build_charges_context(request)
    # Si appel direct sans HTMX → page complète
    if request.headers.get("HX-Request") != "true":
        return render(request, "charges/charges_list.html", ctx)
    return render(request, "charges/includes/charges_list_wrapper.html", ctx)

@login_required
@admin_required
def ajouter_charge(request):
    if request.method == 'POST':
        date = request.POST.get('date')
        page_id = request.POST.get('page')
        page_instance = Pages.objects.get(id=page_id) if page_id else None
        total_lignes = int(request.POST.get('total_lignes', 0))

        for i in range(total_lignes):
            libelle_id = request.POST.get(f'libelle_{i}')
            if not libelle_id:
                continue  # Skip empty lines

            Charge.objects.create(
                date=date,
                page=page_instance,
                libelle_id=libelle_id,
                pu=int(request.POST.get(f'pu_{i}', 0)),
                quantite=int(request.POST.get(f'quantite_{i}', 0)),
                montant=int(request.POST.get(f'montant_{i}', 0)),
                remarque=request.POST.get(f'remarque_{i}', ''),
                paiement_id=request.POST.get(f'paiement_{i}')
            )

        return redirect('charges_list')

@login_required
@admin_required
def modifier_charge(request, pk):
    charge = get_object_or_404(Charge, pk=pk)
    if charge.statut_publication == "supprimé":
        messages.warning(request, "Cette charge a été supprimée et ne peut pas être modifié.")
        return redirect("charges_list")
    if request.method == "POST":
        charge.date = request.POST.get("date")
        charge.page_id = request.POST.get("page") or None  
        charge.libelle_id = request.POST.get("libelle")
        charge.pu = request.POST.get("pu")
        charge.quantite = request.POST.get("quantite")
        charge.montant = request.POST.get("montant")
        charge.remarque = request.POST.get("remarque")
        charge.paiement_id = request.POST.get("paiement")
        charge.save()
        return redirect("charges_list")

    context = {
        "charge": charge,
        "plans": PlanDesComptes.objects.all().order_by('compte_numero'),
        "caisses": Caisse.objects.all(),
        "pages": Pages.objects.all(),  
    }
    return render(request, "charges/charges_list.html", context)

@login_required
@admin_required
def supprimer_charge(request, pk):
    charge = get_object_or_404(Charge, pk=pk)
    if charge.statut_publication == "supprimé":
        messages.warning(request, "Cette charge a déjà été supprimée.")
        return redirect("charges_list")
    
    if request.method == "POST":
        # charge.delete()
        charge.soft_delete()
        return redirect("charges_list")
    return render(request, "charges/charges_list.html", {"objet": charge, "type_objet": "Charge"})

@login_required
@admin_required
def supprimer_definitive_charge(request, pk):
    charge = get_object_or_404(Charge, pk=pk)

    if request.method == "POST":
        password = request.POST.get("password")
        user = authenticate(username=request.user.username, password=password)

        if user is None:
            messages.warning(request, "Mot de passe incorrect. Suppression annulée.")
            return redirect("charges_list")

        charge.delete()
        messages.success(request, "Charge supprimée définitivement.")
        return redirect("charges_list")

    return render(request, "charges/charges_list.html", {"objet": charge, "type_objet": "Charge"})

@login_required
@admin_required
def restaurer_charge(request, pk):
    charge = get_object_or_404(Charge, pk=pk)

    if charge.statut_publication != "supprimé":
        messages.info(request, "Cette charge n'est pas supprimée.")
        return redirect("charges_list")

    if request.method == "POST":
        password = request.POST.get("password")
        user = authenticate(username=request.user.username, password=password)

        if user is None:
            messages.warning(request, "Mot de passe incorrect. Restauration annulée.")
            return redirect("charges_list")

        charge.restore(user=request.user)
        messages.success(request, "Charge restaurée avec succès.")
        return redirect("charges_list")

    return render(request, "charges/charges_list.html", {"objet": charge, "type_objet": "Charge"})
