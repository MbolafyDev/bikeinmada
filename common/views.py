from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from common.decorators import admin_required
from .models import Pages, Caisse, PlanDesComptes

@login_required
@admin_required
def configuration_view(request):
    pages = Pages.objects.all().order_by('nom')
    caisses = Caisse.objects.all()
    plans = PlanDesComptes.objects.all().order_by('compte_numero')
    return render(request, 'common/configuration.html', {
        'pages': pages,
        'caisses': caisses,
        'plans': plans,
        'type_choices': Pages.TYPE_CHOICES,   # ➕ pour alimenter les <option>
    })

@login_required
@admin_required
@require_POST
def ajouter_page(request):
    Pages.objects.create(
        nom=request.POST['nom'],
        contact=request.POST['contact'],
        lien=request.POST.get('lien'),
        logo=request.FILES.get('logo'),
        type=request.POST.get('type') or 'VENTE'  # ➕
    )
    return redirect('configuration')

@login_required
@admin_required
@require_POST
def modifier_page(request, pk):
    page = get_object_or_404(Pages, pk=pk)
    page.nom = request.POST.get("nom")
    page.contact = request.POST.get("contact")
    page.lien = request.POST.get("lien")
    page.type = request.POST.get("type") or page.type   # ➕
    if 'logo' in request.FILES:
        page.logo = request.FILES['logo']
    page.save()
    return redirect('configuration')

@login_required
@admin_required
@require_POST
def supprimer_page(request, pk):
    page = get_object_or_404(Pages, pk=pk)
    page.delete()
    return redirect('configuration')

@login_required
@admin_required
@require_POST
def ajouter_caisse(request):
    Caisse.objects.create(
        nom=request.POST['nom'],
        responsable=request.POST['responsable'],
        solde_initial=request.POST.get('solde_initial', 0)
    )
    return redirect('configuration')

@login_required
@admin_required
@require_POST
def modifier_caisse(request, pk):
    caisse = get_object_or_404(Caisse, pk=pk)
    caisse.nom = request.POST.get("nom")
    caisse.responsable = request.POST.get("responsable")
    caisse.solde_initial = request.POST.get("solde_initial", 0)
    caisse.save()
    return redirect('configuration')

@login_required
@admin_required
@require_POST
def supprimer_caisse(request, pk):
    caisse = get_object_or_404(Caisse, pk=pk)
    caisse.delete()
    return redirect('configuration')

@login_required
@admin_required
@require_POST
def ajouter_plan(request):
    PlanDesComptes.objects.create(
        compte_numero=request.POST['compte_numero'],
        libelle=request.POST['libelle']
    )
    return redirect('configuration')

@login_required
@admin_required
@require_POST
def modifier_plan(request, pk):
    plan = get_object_or_404(PlanDesComptes, pk=pk)
    plan.compte_numero = request.POST.get("compte_numero")
    plan.libelle = request.POST.get("libelle")
    plan.save()
    return redirect('configuration')

@login_required
@admin_required
@require_POST
def supprimer_plan(request, pk):
    plan = get_object_or_404(PlanDesComptes, pk=pk)
    plan.delete()
    return redirect('configuration')