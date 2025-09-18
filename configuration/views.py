# configuration/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from django.http import Http404, JsonResponse, QueryDict, HttpResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q

from common.decorators import admin_required
from common.models import Pages, Caisse, PlanDesComptes
from articles.models import Categorie, Taille, Couleur

# Profil (depuis l’app users)
from users.forms import ProfilForm

# Livraison (modèles + constantes + formulaire)
from livraison.models import (
    Livreur, Livraison,
    CATEGORIE_CHOIX,
    FRAIS_LIVRAISON_PAR_DEFAUT,
    FRAIS_LIVREUR_PAR_DEFAUT,
)
from livraison.forms import LivreurForm

# ✅ Rôles & Utilisateurs (depuis users)
from users.models import Role, CustomUser


# -------------------------------
# Normalisation & prédicats d'accès (UN SEUL point de vérité)
# -------------------------------
ADMIN_ROLE_ALIASES = {"admin", "administrateur", "superadmin"}

def _normalize_role_label(label: str) -> str:
    return (label or "").strip().lower()

def is_admin_user(user) -> bool:
    """
    ➜ Seuls: superuser OU rôle texte dans ADMIN_ROLE_ALIASES.
      - is_staff est ignoré volontairement
      - 'Community Manager', 'Commercial', etc. NE sont PAS admin
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    r = getattr(user, "role", None)
    role_label = _normalize_role_label(getattr(r, "role", None))
    return role_label in ADMIN_ROLE_ALIASES


# Alias interne pour compatibilité (évitons les divergences)
def _has_admin_role(user) -> bool:
    return is_admin_user(user)


# -------------------------------
# Sections disponibles
# -------------------------------
SECTIONS = (
    "pages",
    "caisses",
    "plans",
    "profil",
    "livreurs",
    "frais",
    "articles",
    "roles",         # 🔒 admin-only (protégé ci-dessous)
    "utilisateurs",  # 🔒 admin-only (protégé ci-dessous)
)


# -------------------------------
# Helper : construire le contexte d’une section
# -------------------------------
def _get_section_context(request, section):
    # ⚠️ Une seule variable d’accès, pilotée par is_admin_user()
    is_admin_like = is_admin_user(request.user)

    if section == "pages":
        return ("configuration/includes/configuration_pages.html", {
            "pages": Pages.objects.all().order_by("nom"),
            "type_choices": Pages.TYPE_CHOICES,
            "is_admin": is_admin_like,
        })

    if section == "caisses":
        return ("configuration/includes/configuration_caisses.html", {
            "caisses": Caisse.objects.all().order_by("nom"),
            "is_admin": is_admin_like,
        })

    if section == "plans":
        return ("configuration/includes/configuration_plans.html", {
            "plans": PlanDesComptes.objects.all().order_by("compte_numero"),
            "is_admin": is_admin_like,
        })

    if section == "profil":
        return ("configuration/includes/configuration_profil.html", {
            "form": ProfilForm(instance=request.user),
            "u": request.user,
            "is_admin": is_admin_like,
        })

    if section == "livreurs":
        return ("configuration/includes/configuration_livreurs.html", {
            "livreurs": Livreur.objects.all().order_by("nom"),
            "is_admin": is_admin_like,
        })

    if section == "articles":
        return ("configuration/includes/configuration_articles.html", {
            "categories": Categorie.objects.all().order_by("categorie"),
            "tailles": Taille.objects.all().order_by("taille"),
            "couleurs": Couleur.objects.all().order_by("couleur"),
            "is_admin": is_admin_like,
        })

    if section == "frais":
        lieu_recherche = (request.GET.get('lieu') or '').strip()
        categorie_filtre = request.GET.get('categorie') or ''

        qs = Livraison.objects.all()
        if lieu_recherche:
            qs = qs.filter(lieu__icontains=lieu_recherche)
        if categorie_filtre:
            qs = qs.filter(categorie=categorie_filtre)
        qs = qs.order_by('lieu')

        paginator = Paginator(qs, 30)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        params = request.GET.copy()
        params["tab"] = "frais"
        clean_params = QueryDict(mutable=True)
        for key, values in params.lists():
            if key == 'page':
                continue
            clean_values = [v for v in values if (v or "").strip()]
            if clean_values:
                clean_params.setlist(key, clean_values)
        extra_querystring = ('&' + clean_params.urlencode()) if clean_params else '&tab=frais'

        return ("configuration/includes/configuration_frais.html", {
            "page_obj": page_obj,
            "categories": CATEGORIE_CHOIX,
            "lieu_recherche": lieu_recherche,
            "categorie_filtre": categorie_filtre,
            "extra_querystring": extra_querystring,
            "is_admin": is_admin_like,
            "FRAIS_LIVRAISON_PAR_DEFAUT": FRAIS_LIVRAISON_PAR_DEFAUT,
            "FRAIS_LIVREUR_PAR_DEFAUT": FRAIS_LIVREUR_PAR_DEFAUT,
        })

    if section == "roles":
        return ("configuration/includes/configuration_roles.html", {
            "roles": Role.objects.all().order_by("role"),
            "is_admin": is_admin_like,
        })

    if section == "utilisateurs":
        q = (request.GET.get("q") or "").strip()
        role_id = request.GET.get("role") or ""
        only_active = request.GET.get("only_active") == "on"
        only_waiting_validation = request.GET.get("only_waiting_validation") == "on"

        users_qs = CustomUser.objects.select_related("role").all()

        if q:
            users_qs = users_qs.filter(
                Q(username__icontains=q) |
                Q(email__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(telephone__icontains=q) |
                Q(adresse__icontains=q)
            )

        if role_id:
            users_qs = users_qs.filter(role_id=role_id)

        if only_active:
            users_qs = users_qs.filter(is_active=True)

        if only_waiting_validation:
            users_qs = users_qs.filter(is_validated_by_admin=False)

        users_qs = users_qs.order_by("username")

        paginator = Paginator(users_qs, 25)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        return ("configuration/includes/configuration_utilisateurs.html", {
            "page_obj": page_obj,
            "roles": Role.objects.all().order_by("role"),
            "q": q,
            "role_id": role_id,
            "only_active": only_active,
            "only_waiting_validation": only_waiting_validation,
            "is_admin": is_admin_like,
        })

    raise Http404("Section inconnue")


# -------------------------------
# Page Configuration (shell) + endpoint HTMX pour sections
# -------------------------------
@login_required
def configuration_view(request):
    section = request.GET.get("tab", "pages")
    if section not in SECTIONS:
        section = "pages"

    # 🔒 Interdire 'roles' et 'utilisateurs' aux non-admin (strict)
    can_manage_admin_things = is_admin_user(request.user)
    if section in {"roles", "utilisateurs"} and not can_manage_admin_things:
        messages.warning(request, "Accès refusé : vous n’avez pas les droits pour cette section.")
        section = "pages"

    partial_tpl, partial_ctx = _get_section_context(request, section)

    ctx = {
        "selected_section": section,
        "partial_template": partial_tpl,
        "can_manage_admin_things": can_manage_admin_things,
        **partial_ctx
    }
    return render(request, "configuration/configuration.html", ctx)


@login_required
def configuration_section(request, section: str):
    if section not in SECTIONS:
        raise Http404("Section inconnue")

    if section in {"roles", "utilisateurs"} and not is_admin_user(request.user):
        if not request.headers.get("HX-Request"):
            messages.warning(request, "Accès refusé : vous n’avez pas les droits pour cette section.")
            return redirect(f"{reverse('configuration')}?tab=pages")
        response = JsonResponse({"error": "forbidden", "message": "Permissions insuffisantes."})
        response.status_code = 403
        return response

    partial_tpl, partial_ctx = _get_section_context(request, section)

    if not request.headers.get("HX-Request"):
        ctx = {
            "selected_section": section,
            "partial_template": partial_tpl,
            "can_manage_admin_things": is_admin_user(request.user),
            **partial_ctx
        }
        return render(request, "configuration/configuration.html", ctx)

    return render(request, partial_tpl, {**partial_ctx, "is_htmx": True})


# -------------------------------
# Actions PAGES
# -------------------------------
@login_required
@admin_required
@require_POST
def ajouter_page(request):
    try:
        Pages.objects.create(
            nom=request.POST['nom'],
            contact=request.POST['contact'],
            lien=request.POST.get('lien'),
            logo=request.FILES.get('logo'),
            type=request.POST.get('type') or 'VENTE'
        )
        messages.success(request, "Page ajoutée avec succès ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout de la page : {e}")
    return redirect(f"{reverse('configuration')}?tab=pages")


@login_required
@admin_required
@require_POST
def modifier_page(request, pk):
    try:
        page = get_object_or_404(Pages, pk=pk)
        page.nom = request.POST.get("nom")
        page.contact = request.POST.get("contact")
        page.lien = request.POST.get("lien")
        page.type = request.POST.get("type") or page.type
        if 'logo' in request.FILES:
            page.logo = request.FILES['logo']
        page.save()
        messages.success(request, f"Page « {page.nom} » modifiée ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification : {e}")
    return redirect(f"{reverse('configuration')}?tab=pages")


@login_required
@admin_required
@require_POST
def supprimer_page(request, pk):
    try:
        page = get_object_or_404(Pages, pk=pk)
        nom = page.nom
        page.soft_delete(user=request.user)
        messages.success(request, f"Page « {nom} » supprimée 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression : {e}")
    return redirect(f"{reverse('configuration')}?tab=pages")


# -------------------------------
# Actions CAISSES
# -------------------------------
@login_required
@admin_required
@require_POST
def ajouter_caisse(request):
    try:
        Caisse.objects.create(
            nom=request.POST['nom'],
            responsable=request.POST['responsable'],
            solde_initial=request.POST.get('solde_initial', 0)
        )
        messages.success(request, "Caisse ajoutée avec succès ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout de la caisse : {e}")
    return redirect(f"{reverse('configuration')}?tab=caisses")


@login_required
@admin_required
@require_POST
def modifier_caisse(request, pk):
    try:
        caisse = get_object_or_404(Caisse, pk=pk)
        caisse.nom = request.POST.get("nom")
        caisse.responsable = request.POST.get("responsable")
        caisse.solde_initial = request.POST.get("solde_initial", 0)
        caisse.save()
        messages.success(request, f"Caisse « {caisse.nom} » modifiée ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification : {e}")
    return redirect(f"{reverse('configuration')}?tab=caisses")


@login_required
@admin_required
@require_POST
def supprimer_caisse(request, pk):
    try:
        caisse = get_object_or_404(Caisse, pk=pk)
        nom = caisse.nom
        caisse.soft_delete(user=request.user)
        messages.success(request, f"Caisse « {nom} » supprimée 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression : {e}")
    return redirect(f"{reverse('configuration')}?tab=caisses")


# -------------------------------
# Actions PLAN DES COMPTES
# -------------------------------
@login_required
@admin_required
@require_POST
def ajouter_plan(request):
    try:
        PlanDesComptes.objects.create(
            compte_numero=request.POST['compte_numero'],
            libelle=request.POST['libelle']
        )
        messages.success(request, "Compte ajouté avec succès ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout du compte : {e}")
    return redirect(f"{reverse('configuration')}?tab=plans")


@login_required
@admin_required
@require_POST
def modifier_plan(request, pk):
    try:
        plan = get_object_or_404(PlanDesComptes, pk=pk)
        plan.compte_numero = request.POST.get("compte_numero")
        plan.libelle = request.POST.get("libelle")
        plan.save()
        messages.success(request, f"Compte « {plan.compte_numero} » modifié ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification : {e}")
    return redirect(f"{reverse('configuration')}?tab=plans")


@login_required
@admin_required
@require_POST
def supprimer_plan(request, pk):
    try:
        plan = get_object_or_404(PlanDesComptes, pk=pk)
        num = plan.compte_numero
        plan.soft_delete(user=request.user)
        messages.success(request, f"Compte « {num} » supprimé 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression du compte : {e}")
    return redirect(f"{reverse('configuration')}?tab=plans")


# -------------------------------
# Actions PROFIL
# -------------------------------
@login_required
@require_POST
def configuration_profil_update(request):
    form = ProfilForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour avec succès ✅")
    else:
        messages.warning(request, "Échec de la mise à jour du profil. Corrigez les erreurs puis réessayez.")
    return redirect(f"{reverse('configuration')}?tab=profil")


# -------------------------------
# Actions LIVREURS
# -------------------------------
@login_required
@admin_required
@require_POST
def ajouter_livreur(request):
    try:
        form = LivreurForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Livreur ajouté avec succès ✅")
        else:
            messages.warning(request, f"Erreur de validation : {form.errors}")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout : {e}")
    return redirect(f"{reverse('configuration')}?tab=livreurs")


@login_required
@admin_required
@require_POST
def modifier_livreur(request, id):
    try:
        livreur = get_object_or_404(Livreur, id=id)
        form = LivreurForm(request.POST, instance=livreur)
        if form.is_valid():
            form.save()
            messages.success(request, f"Livreur « {livreur.nom} » modifié ✅")
        else:
            messages.warning(request, f"Erreur de validation : {form.errors}")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification : {e}")
    return redirect(f"{reverse('configuration')}?tab=livreurs")


@login_required
@admin_required
@require_POST
def supprimer_livreur(request, id):
    try:
        livreur = get_object_or_404(Livreur, id=id)
        nom = livreur.nom
        livreur.soft_delete(user=request.user)
        messages.success(request, f"Livreur « {nom} » supprimé 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression : {e}")
    return redirect(f"{reverse('configuration')}?tab=livreurs")


# -------------------------------
# Actions FRAIS DE LIVRAISON
# -------------------------------
@login_required
@require_POST
def frais_livraison_ajouter(request):
    lieu = (request.POST.get('lieu') or '').strip()
    categorie = (request.POST.get('categorie') or '').strip()
    frais_livraison = (request.POST.get('frais_livraison') or '').strip()
    frais_livreur = (request.POST.get('frais_livreur') or '').strip()

    if not lieu or not categorie:
        messages.warning(request, "Champs obligatoires manquants.")
        return redirect(f"{reverse('configuration')}?tab=frais")

    try:
        frais_livraison_val = int(frais_livraison) if frais_livraison else FRAIS_LIVRAISON_PAR_DEFAUT.get(categorie, 0)
    except (TypeError, ValueError):
        frais_livraison_val = FRAIS_LIVRAISON_PAR_DEFAUT.get(categorie, 0)

    try:
        frais_livreur_val = int(frais_livreur) if frais_livreur else FRAIS_LIVREUR_PAR_DEFAUT.get(categorie, 0)
    except (TypeError, ValueError):
        frais_livreur_val = FRAIS_LIVREUR_PAR_DEFAUT.get(categorie, 0)

    try:
        Livraison.objects.create(
            lieu=lieu,
            categorie=categorie,
            frais_livraison=frais_livraison_val,
            frais_livreur=frais_livreur_val
        )
        messages.success(request, "Lieu ajouté avec succès ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout : {e}")

    return redirect(f"{reverse('configuration')}?tab=frais")


@login_required
@require_POST
def frais_livraison_modifier(request, id):
    frais = get_object_or_404(Livraison, id=id)

    lieu = (request.POST.get('lieu') or '').strip()
    categorie = (request.POST.get('categorie') or '').strip()
    frais_livraison = (request.POST.get('frais_livraison') or '').strip()
    frais_livreur = (request.POST.get('frais_livreur') or '').strip()

    if not lieu or not categorie:
        messages.warning(request, "Champs obligatoires manquants.")
        return redirect(f"{reverse('configuration')}?tab=frais")

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

    try:
        frais.save()
        messages.success(request, f"Lieu « {frais.lieu} » modifié ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification : {e}")

    return redirect(f"{reverse('configuration')}?tab=frais")


@login_required
@admin_required
@require_POST
def frais_livraison_supprimer(request, id):
    try:
        frais = get_object_or_404(Livraison, id=id)
        lieu = frais.lieu
        frais.soft_delete(user=request.user)
        messages.success(request, f"Lieu « {lieu} » supprimé 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression : {e}")
    return redirect(f"{reverse('configuration')}?tab=frais")


# -------------------------------
# Actions ARTICLES (catégories / tailles / couleurs)
# -------------------------------
@login_required
@admin_required
@require_POST
def ajouter_categorie(request):
    try:
        Categorie.objects.create(categorie=request.POST['categorie'])
        messages.success(request, "Catégorie ajoutée avec succès ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout de la catégorie : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


@login_required
@admin_required
@require_POST
def modifier_categorie(request, pk):
    try:
        categorie = get_object_or_404(Categorie, pk=pk)
        categorie.categorie = request.POST.get("categorie")
        categorie.save()
        messages.success(request, f"Catégorie « {categorie.categorie} » modifiée ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


@login_required
@admin_required
@require_POST
def supprimer_categorie(request, pk):
    try:
        categorie = get_object_or_404(Categorie, pk=pk)
        nom = categorie.categorie
        categorie.soft_delete(user=request.user)
        messages.success(request, f"Catégorie « {nom} » supprimée 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


@login_required
@admin_required
@require_POST
def ajouter_taille(request):
    try:
        Taille.objects.create(taille=request.POST['taille'])
        messages.success(request, "Taille ajoutée avec succès ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout de la taille : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


@login_required
@admin_required
@require_POST
def modifier_taille(request, pk):
    try:
        taille = get_object_or_404(Taille, pk=pk)
        taille.taille = request.POST.get("taille")
        taille.save()
        messages.success(request, f"Taille « {taille.taille} » modifiée ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


@login_required
@admin_required
@require_POST
def supprimer_taille(request, pk):
    try:
        taille = get_object_or_404(Taille, pk=pk)
        nom = taille.taille
        taille.soft_delete(user=request.user)
        messages.success(request, f"Taille « {nom} » supprimée 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


@login_required
@admin_required
@require_POST
def ajouter_couleur(request):
    try:
        Couleur.objects.create(couleur=request.POST['couleur'])
        messages.success(request, "Couleur ajoutée avec succès ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout de la couleur : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


@login_required
@admin_required
@require_POST
def modifier_couleur(request, pk):
    try:
        couleur = get_object_or_404(Couleur, pk=pk)
        couleur.couleur = request.POST.get("couleur")
        couleur.save()
        messages.success(request, f"Couleur « {couleur.couleur} » modifiée ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


@login_required
@admin_required
@require_POST
def supprimer_couleur(request, pk):
    try:
        couleur = get_object_or_404(Couleur, pk=pk)
        nom = couleur.couleur
        couleur.soft_delete(user=request.user)
        messages.success(request, f"Couleur « {nom} » supprimée 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression : {e}")
    return redirect(f"{reverse('configuration')}?tab=articles")


# -------------------------------
# ✅ Actions ROLES (protégées strictement)
# -------------------------------
@login_required
@user_passes_test(is_admin_user)
@require_POST
def ajouter_role(request):
    lib = (request.POST.get("role") or "").strip()
    if not lib:
        messages.warning(request, "Le nom du rôle est requis.")
        return redirect(f"{reverse('configuration')}?tab=roles")
    try:
        lib_norm = lib.title()
        Role.objects.get_or_create(role=lib_norm)
        messages.success(request, f"Rôle « {lib_norm} » ajouté ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de l’ajout du rôle : {e}")
    return redirect(f"{reverse('configuration')}?tab=roles")


@login_required
@user_passes_test(is_admin_user)
@require_POST
def modifier_role(request, pk):
    lib = (request.POST.get("role") or "").strip()
    if not lib:
        messages.warning(request, "Le nom du rôle est requis.")
        return redirect(f"{reverse('configuration')}?tab=roles")
    try:
        r = get_object_or_404(Role, pk=pk)
        r.role = lib.title()
        r.save()
        messages.success(request, f"Rôle « {r.role} » modifié ✅")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la modification du rôle : {e}")
    return redirect(f"{reverse('configuration')}?tab=roles")


@login_required
@user_passes_test(is_admin_user)
@require_POST
def supprimer_role(request, pk):
    try:
        r = get_object_or_404(Role, pk=pk)
        nom = r.role
        r.delete()
        messages.success(request, f"Rôle « {nom} » supprimé 🗑️")
    except Exception as e:
        messages.warning(request, f"Erreur lors de la suppression du rôle : {e}")
    return redirect(f"{reverse('configuration')}?tab=roles")


# -------------------------------
# ✅ Actions UTILISATEURS (inline via HTMX)
# -------------------------------
@login_required
@user_passes_test(is_admin_user)  # strict: superuser ou rôle admin/administrateur/superadmin
@require_POST
def config_user_update(request, user_id: int):
    u: CustomUser = get_object_or_404(CustomUser, pk=user_id)
    changed_fields = []

    def last_value(name: str):
        vals = request.POST.getlist(name)
        return vals[-1] if vals else None

    def as_bool(val) -> bool:
        if val is None:
            return False
        return str(val).strip().lower() in {"1", "true", "on", "yes"}

    # --- rôle
    if "role_id" in request.POST:
        role_id = last_value("role_id") or None
        new_role = get_object_or_404(Role, pk=role_id) if role_id else None
        if u.role_id != (new_role.id if new_role else None):
            u.role = new_role
            changed_fields.append("role")

    # --- is_active
    if "is_active" in request.POST:
        new_active = as_bool(last_value("is_active"))
        if bool(u.is_active) != new_active:
            u.is_active = new_active
            changed_fields.append("is_active")

    # --- is_validated_by_admin (valider active aussi le compte)
    if "is_validated_by_admin" in request.POST:
        new_valid = as_bool(last_value("is_validated_by_admin"))
        if bool(u.is_validated_by_admin) != new_valid:
            u.is_validated_by_admin = new_valid
            changed_fields.append("is_validated_by_admin")
            if new_valid and not u.is_active:
                u.is_active = True
                changed_fields.append("is_active")

    if changed_fields:
        u.save(update_fields=list(set(changed_fields)))

    if request.headers.get("HX-Request"):
        resp = HttpResponse(status=204)
        resp["HX-Trigger"] = '{"flash":{"type":"success","message":"Utilisateur mis à jour"}}'
        return resp
    else:
        messages.success(request, "Utilisateur mis à jour ✅")
        return redirect(f"{reverse('configuration')}?tab=utilisateurs")


@login_required
@user_passes_test(is_admin_user)
@require_POST
def config_user_delete(request, user_id: int):
    target = get_object_or_404(CustomUser, pk=user_id)

    # Interdictions & garde-fous
    if target.id == request.user.id:
        if request.headers.get("HX-Request"):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = '{"flash":{"type":"warning","message":"Vous ne pouvez pas vous supprimer."}}'
            return resp
        messages.warning(request, "Vous ne pouvez pas vous supprimer.")
        return redirect(f"{reverse('configuration')}?tab=utilisateurs")

    if target.is_superuser and not request.user.is_superuser:
        if request.headers.get("HX-Request"):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = '{"flash":{"type":"danger","message":"Action refusée : superutilisateur."}}'
            return resp
        messages.warning(request, "Action refusée : superutilisateur.")
        return redirect(f"{reverse('configuration')}?tab=utilisateurs")

    target_role = _normalize_role_label(getattr(getattr(target, "role", None), "role", ""))
    if target_role in ADMIN_ROLE_ALIASES and not request.user.is_superuser:
        if request.headers.get("HX-Request"):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = '{"flash":{"type":"danger","message":"Seul un superuser peut supprimer un compte admin."}}'
            return resp
        messages.warning(request, "Seul un superuser peut supprimer un compte admin.")
        return redirect(f"{reverse('configuration')}?tab=utilisateurs")

    username = target.username
    try:
        target.delete()
        if request.headers.get("HX-Request"):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = f'{{"flash":{{"type":"success","message":"Utilisateur « {username} » supprimé"}}}}'
            return resp
        messages.success(request, f"Utilisateur « {username} » supprimé 🗑️")
    except Exception as e:
        if request.headers.get("HX-Request"):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = f'{{"flash":{{"type":"danger","message":"Erreur suppression : {str(e)}"}}}}'
            return resp
        messages.warning(request, f"Erreur suppression : {e}")

    return redirect(f"{reverse('configuration')}?tab=utilisateurs")
