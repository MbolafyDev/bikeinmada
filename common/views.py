from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from common.decorators import admin_required
from .models import Pages, Caisse, PlanDesComptes
from users.forms import ProfilForm
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.core.paginator import Paginator

def _redir_to_next_or(default_response, request):
  
    nxt = request.POST.get('next')
    if nxt:
        return HttpResponseRedirect(nxt)
    return default_response

def _redir_pages():
    return HttpResponseRedirect(f"{reverse('configuration')}?tab=pages#tab-pages")

def _redir_caisses():
    return HttpResponseRedirect(f"{reverse('configuration')}?tab=caisses#tab-caisses")

def _redir_plans():
    return HttpResponseRedirect(f"{reverse('configuration')}?tab=plans#tab-plans")


@login_required
@admin_required
def configuration_view(request):
    active_tab = request.GET.get('tab', 'profil')
    form = ProfilForm(instance=request.user)

    # Querysets
    pages_qs   = Pages.objects.all().order_by('nom')
    caisses_qs = Caisse.objects.all().order_by('nom')
    plans_qs   = PlanDesComptes.objects.all().order_by('compte_numero')

    # Tailles par page (avec valeurs par défaut)
    per_pages   = int(request.GET.get('pp_pages', 3))
    per_caisses = int(request.GET.get('pp_caisses', 3))
    per_plans   = int(request.GET.get('pp_plans', 3))

    # Paginators
    pages_p   = Paginator(pages_qs, per_pages)
    caisses_p = Paginator(caisses_qs, per_caisses)
    plans_p   = Paginator(plans_qs, per_plans)

    # ✅ Accepte aussi ?page=... pour l'onglet actif (fallback si page_X non fourni)
    generic_page = request.GET.get('page')

    pages_num   = request.GET.get('page_pages')   or (generic_page if active_tab == 'pages'   else 1)
    caisses_num = request.GET.get('page_caisses') or (generic_page if active_tab == 'caisses' else 1)
    plans_num   = request.GET.get('page_plans')   or (generic_page if active_tab == 'plans'   else 1)

    # Page objects
    pages_page   = pages_p.get_page(pages_num)
    caisses_page = caisses_p.get_page(caisses_num)
    plans_page   = plans_p.get_page(plans_num)

    # QS minimales pour rester sur le bon onglet
    pages_qs_params   = "tab=pages"
    caisses_qs_params = "tab=caisses"
    plans_qs_params   = "tab=plans"

    return render(request, 'common/configuration.html', {
        'user': request.user,
        'form': form,
        'type_choices': Pages.TYPE_CHOICES,
        'active_tab': active_tab,
        'is_admin': True,

        # objets paginés
        'pages_page': pages_page,
        'caisses_page': caisses_page,
        'plans_page': plans_page,

        # querystrings pour la pagination
        'pages_qs_params': pages_qs_params,
        'caisses_qs_params': caisses_qs_params,
        'plans_qs_params': plans_qs_params,
    })

@login_required
@admin_required
@require_POST
def ajouter_page(request):
    page = Pages.objects.create(
        nom=request.POST.get('nom', '').strip(),
        contact=request.POST.get('contact', '').strip(),
        lien=request.POST.get('lien') or None,
        logo=request.FILES.get('logo'),
        type=request.POST.get('type') or 'VENTE'
    )
    messages.success(request, f"Page « {page.nom} » ajoutée avec succès.")
    return _redir_pages()

@login_required
@admin_required
@require_POST
def modifier_page(request, pk):
    page = get_object_or_404(Pages, pk=pk)
    page.nom = request.POST.get("nom", page.nom).strip()
    page.contact = request.POST.get("contact", page.contact).strip()
    page.lien = request.POST.get("lien") or None
    page.type = request.POST.get("type") or page.type
    if 'logo' in request.FILES:
        page.logo = request.FILES['logo']
    page.save()
    messages.success(request, f"Page « {page.nom} » modifiée avec succès.")
    return _redir_pages()

@login_required
@admin_required
@require_POST
def supprimer_page(request, pk):
    page = get_object_or_404(Pages, pk=pk)
    nom = page.nom
    page.delete()
    messages.success(request, f"Page « {nom} » supprimée.")
    return _redir_pages()

@login_required
@admin_required
@require_POST
def ajouter_caisse(request):
    Caisse.objects.create(
        nom=request.POST['nom'],
        responsable=request.POST['responsable'],
        solde_initial=request.POST.get('solde_initial', 0)
    )
    messages.success(request, "Caisse ajoutée avec succès.")
    return _redir_to_next_or(_redir_caisses(), request)

@login_required
@admin_required
@require_POST
def modifier_caisse(request, pk):
    caisse = get_object_or_404(Caisse, pk=pk)
    caisse.nom = request.POST.get("nom")
    caisse.responsable = request.POST.get("responsable")
    caisse.solde_initial = request.POST.get("solde_initial", 0)
    caisse.save()
    messages.success(request, f"Caisse « {caisse.nom} » modifiée.")
    return _redir_to_next_or(_redir_caisses(), request)

@login_required
@admin_required
@require_POST
def supprimer_caisse(request, pk):
    caisse = get_object_or_404(Caisse, pk=pk)
    nom = caisse.nom
    caisse.delete()
    messages.success(request, f"Caisse « {nom} » supprimée.")
    return _redir_to_next_or(_redir_caisses(), request)

@login_required
@admin_required
@require_POST
def ajouter_plan(request):
    PlanDesComptes.objects.create(
        compte_numero=request.POST['compte_numero'],
        libelle=request.POST['libelle']
    )
    messages.success(request, "Compte ajouté avec succès.")
    return _redir_to_next_or(_redir_plans(), request)

@login_required
@admin_required
@require_POST
def modifier_plan(request, pk):
    plan = get_object_or_404(PlanDesComptes, pk=pk)
    plan.compte_numero = request.POST.get("compte_numero", plan.compte_numero)
    plan.libelle = request.POST.get("libelle", plan.libelle)
    plan.save()
    messages.success(request, f"Compte « {plan.compte_numero} – {plan.libelle} » modifié.")
    return _redir_to_next_or(_redir_plans(), request)

@login_required
@admin_required
@require_POST
def supprimer_plan(request, pk):
    plan = get_object_or_404(PlanDesComptes, pk=pk)
    num, lib = plan.compte_numero, plan.libelle
    plan.delete()
    messages.success(request, f"Compte « {num} – {lib} » supprimé.")
    return _redir_to_next_or(_redir_plans(), request)