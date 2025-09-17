from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q, F, IntegerField, Value, Case, When
from django.db.models.functions import TruncMonth
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.utils.timezone import now
from datetime import date
from calendar import monthrange
from django.contrib import messages
from collections import defaultdict
from common.decorators import admin_required
from common.utils import is_admin
from caisses.models import Caisse, Versement
from caisses.utils import calculer_totaux_caisses
from ventes.models import Vente, Commande, LigneCommande
from achats.models import Achat
from charges.models import Charge
from common.models import Caisse, Pages
from .models import MouvementCaisse


@login_required
@admin_required
def etat_caisses(request):
    # ------------------------------------------------------------------ #
    # 1)  ETAT INDIVIDUEL DES CAISSES  (GLOBAUX, NON FILTRÉS)
    # ------------------------------------------------------------------ #
    caisses = Caisse.objects.all()
    etats = []

    total_solde_initial = total_entrees = total_achats = 0
    total_charges_caisses = total_versements = total_sorties = 0
    total_solde_final = total_mouvements = 0

    for caisse in caisses:
        ventes_total = (
            Vente.actifs
            .filter(paiement=caisse, commande__statut_vente="Payée")
            .aggregate(total=Sum("montant"))["total"] or 0
        )

        achats_total = (
            Achat.actifs.filter(paiement=caisse)
            .aggregate(total=Sum("lignes_achats__montant"))["total"] or 0
        )

        charges_caisses_total = (
            Charge.actifs
            .filter(paiement=caisse, libelle__compte_numero__startswith="6")
            .aggregate(total=Sum("montant"))["total"] or 0
        )

        versements_total = (
            Versement.actifs.filter(caisse=caisse)
            .aggregate(total=Sum("montant"))["total"] or 0
        )

        mouvements_entree = (
            MouvementCaisse.actifs.filter(caisse_credit_id=caisse.id)
            .aggregate(total=Sum("montant"))["total"] or 0
        )
        mouvements_sortie = (
            MouvementCaisse.actifs.filter(caisse_debit_id=caisse.id)
            .aggregate(total=Sum("montant"))["total"] or 0
        )
        mouvement = mouvements_entree - mouvements_sortie
        total_mouvements += mouvement

        entrees = ventes_total
        sorties = achats_total + charges_caisses_total + versements_total
        solde_final = (
            caisse.solde_initial
            + entrees
            + mouvements_entree
            - sorties
            - mouvements_sortie
        )

        etats.append(
            {
                "caisse": caisse,
                "solde_initial": caisse.solde_initial,
                "entrees": entrees,
                "achats": achats_total,
                "charges_caisses": charges_caisses_total,
                "versements": versements_total,
                "sorties": sorties,
                "solde_final": solde_final,
                "mouvement": mouvement,
            }
        )

        total_solde_initial += caisse.solde_initial
        total_entrees += entrees
        total_achats += achats_total
        total_charges_caisses += charges_caisses_total
        total_versements += versements_total
        total_sorties += sorties
        total_solde_final += solde_final

    # ------------------------------------------------------------------ #
    # ✅  FILTRES Année / Mois pour RÉCAP PAR PAGE + RÉPARTITION CHARGES
    # ------------------------------------------------------------------ #
    year_param = (request.GET.get("year") or "").strip()
    month_param = (request.GET.get("month") or "").strip()

    selected_year = int(year_param) if year_param and year_param.lower() != "tous" else None
    selected_month = int(month_param) if month_param and month_param.lower() != "tous" else None

    # Fenêtre temporelle annuelle
    start_year = end_year = None
    if selected_year:
        start_year = date(selected_year, 1, 1)
        end_year = date(selected_year + 1, 1, 1)  # exclusif

    # Q() par modèle/champ
    # - Commande: date_commande (sur Commande)
    # - LigneCommande: commande__date_commande (sur LC)
    # - Charge: date
    # - Versement: date  (⚠️ adaptez si votre champ diffère)
    commande_date_q = Q()
    commande_date_q_lc = Q()
    chg_date_q = Q()
    vers_date_q = Q()

    if start_year and end_year:
        commande_date_q &= Q(date_commande__gte=start_year, date_commande__lt=end_year)
        commande_date_q_lc &= Q(commande__date_commande__gte=start_year, commande__date_commande__lt=end_year)
        chg_date_q &= Q(date__gte=start_year, date__lt=end_year)
        vers_date_q &= Q(date__gte=start_year, date__lt=end_year)

    if selected_month:
        commande_date_q &= Q(date_commande__month=selected_month)
        commande_date_q_lc &= Q(commande__date_commande__month=selected_month)
        chg_date_q &= Q(date__month=selected_month)
        vers_date_q &= Q(date__month=selected_month)

    # ------------------------------------------------------------------ #
    # 2)  RÉPARTITION DES CHARGES NON AFFECTÉES PAR MOIS & PAR PAGE (FILTRABLE)
    # ------------------------------------------------------------------ #
    charges_qs = Charge.actifs.filter(
        page__isnull=True, libelle__compte_numero__startswith="6"
    )
    if chg_date_q:
        charges_qs = charges_qs.filter(chg_date_q)

    charges_par_mois = dict(
        charges_qs
        .annotate(mois=TruncMonth("date"))
        .values("mois")
        .annotate(total=Sum("montant"))
        .values_list("mois", "total")
    )

    quantites_par_mois_page = defaultdict(lambda: defaultdict(int))
    lignes = (
        LigneCommande.actifs.filter(
            commande__statut_vente="Payée", commande__vente__isnull=False
        )
        .filter(commande_date_q_lc)  # ✅ applique la période sur commande__date_commande
        .annotate(
            mois=TruncMonth("commande__date_commande"),
            page_id=F("commande__page_id"),
        )
        .values("mois", "page_id")
        .annotate(qte=Sum("quantite"))
    )
    for row in lignes:
        quantites_par_mois_page[row["mois"]][row["page_id"]] += row["qte"]

    part_charges_pages = defaultdict(int)     # cumul pour chaque page
    repartition_charges = []                  # détail par mois pour le template
    repartition_totaux = defaultdict(int)     # total cumulé par page

    for mois, montant_charge_mois in charges_par_mois.items():
        parts = {}
        quantites_page = quantites_par_mois_page.get(mois, {})
        total_qte_mois = sum(quantites_page.values()) or 1  # évite /0

        for page_id, qte in quantites_page.items():
            part = (qte / total_qte_mois) * montant_charge_mois
            part_arrondi = int(round(part, -2))  # arrondi à la centaine
            parts[page_id] = part_arrondi
            part_charges_pages[page_id] += part_arrondi
            repartition_totaux[page_id] += part_arrondi

        repartition_charges.append(
            {"mois": mois, "parts": parts, "total": montant_charge_mois}
        )

    repartition_total = sum(charges_par_mois.values())

    # ------------------------------------------------------------------ #
    # 3)  RÉCAPITULATIF PAR PAGE (FILTRABLE)
    # ------------------------------------------------------------------ #
    recap_pages = []
    pages = Pages.objects.filter(type="VENTE")

    total_chiffre_affaire = total_cout_achats = 0
    total_charges_pages = total_versements_pages = 0

    for page in pages:
        # Commandes vendues filtrées par date
        commandes_vendues = Commande.actifs.filter(
            page=page, vente__isnull=False, statut_vente="Payée"
        ).filter(commande_date_q)

        # Ventes (CA) depuis les ventes rattachées à ces commandes
        chiffre_affaire = (
            Vente.actifs.filter(commande__in=commandes_vendues)
            .aggregate(total=Sum("montant"))["total"]
            or 0
        )

        # Achats (coût d’achat) via lignes des commandes filtrées
        lignes_vendues = LigneCommande.actifs.filter(commande__in=commandes_vendues)
        cout_achats = sum(l.quantite * l.prix_achat for l in lignes_vendues)

        # Charges affectées à la page sur la période
        charges_affectees_qs = Charge.actifs.filter(
            page=page, libelle__compte_numero__startswith="6"
        )
        if chg_date_q:
            charges_affectees_qs = charges_affectees_qs.filter(chg_date_q)
        charges_affectees = charges_affectees_qs.aggregate(total=Sum("montant"))["total"] or 0

        # Part des charges communes calculées ci-dessus
        part_charge_non_affectee = part_charges_pages.get(page.id, 0)
        charges_total = charges_affectees + part_charge_non_affectee

        # Versements de la page sur la période
        versements_qs = Versement.actifs.filter(page=page)
        if vers_date_q:
            versements_qs = versements_qs.filter(vers_date_q)
        versements = versements_qs.aggregate(total=Sum("montant"))["total"] or 0

        marge = chiffre_affaire - cout_achats - charges_total
        reste = marge - versements

        total_chiffre_affaire += chiffre_affaire
        total_cout_achats += cout_achats
        total_charges_pages += charges_total
        total_versements_pages += versements

        recap_pages.append(
            {
                "page": page.nom,
                "chiffre_affaire": chiffre_affaire,
                "cout_achats": cout_achats,
                "charges_pages": charges_total,
                "part_charge_non_affectee": part_charge_non_affectee,
                "versements": versements,
                "marge": marge,
                "reste": reste,
                "ecart": total_solde_final - reste,
            }
        )

    recap_pages.append(
        {
            "page": "TOTAL",
            "chiffre_affaire": total_chiffre_affaire,
            "cout_achats": total_cout_achats,
            "charges_pages": total_charges_pages,
            "versements": total_versements_pages,
            "marge": total_chiffre_affaire - total_cout_achats - total_charges_pages,
            "reste": total_chiffre_affaire - total_cout_achats - total_charges_pages - total_versements_pages,
            "ecart": "-",
        }
    )

    # ------------------------------------------------------------------ #
    # 4)  CONTEXTE & RENDER
    # ------------------------------------------------------------------ #
    current_year = now().year
    years_choices = list(range(current_year, current_year - 6, -1))  # 5 dernières années + en cours
    months_choices = [
        (1, "Janvier"), (2, "Février"), (3, "Mars"), (4, "Avril"),
        (5, "Mai"), (6, "Juin"), (7, "Juillet"), (8, "Août"),
        (9, "Septembre"), (10, "Octobre"), (11, "Novembre"), (12, "Décembre"),
    ]

    context = {
        "etats": etats,
        "caisses": caisses,
        "recap_pages": recap_pages,
        "pages": pages,
        "today": now().date(),
        "repartition_charges": repartition_charges,
        "repartition_totaux": dict(repartition_totaux),
        "repartition_total": repartition_total,
        "totaux": {
            "solde_initial": total_solde_initial,
            "entrees": total_entrees,
            "achats": total_achats,
            "charges_caisses": total_charges_caisses,
            "versements": total_versements,
            "mouvements": total_mouvements,
            "sorties": total_sorties,
            "solde_final": total_solde_final,
            "is_admin": is_admin(request.user),
        },
        # ✅ Filtres (pour le template)
        "selected_year": selected_year,
        "selected_month": selected_month,
        "years_choices": years_choices,
        "months_choices": months_choices,
        "is_admin": is_admin(request.user),
    }
    return render(request, "caisses/etat_caisses.html", context)

@login_required
@admin_required
def versements_list(request):
    caisses = Caisse.objects.all()
    pages = Pages.objects.filter(type="VENTE")

    # Récupération des paramètres de filtre
    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")
    caisse_id = request.GET.get("caisse")
    page_id = request.GET.get("page")

    versements = Versement.objects.all().order_by("-date")

    if date_debut:
        versements = versements.filter(date__gte=date_debut)
    if date_fin:
        versements = versements.filter(date__lte=date_fin)
    if caisse_id:
        versements = versements.filter(caisse_id=caisse_id)
    if page_id:
        versements = versements.filter(page_id=page_id)

    context = {
        "versements": versements,
        "caisses": caisses,
        "pages": pages,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "selected_caisse": caisse_id,
        "selected_page": page_id,
        "today": now().date(),
        "is_admin": is_admin(request.user),
    }
    return render(request, "caisses/versements_list.html", context)

@login_required
@admin_required
def ajouter_versement(request):
    if request.method == "POST":
        date = request.POST.get("date") or now().date()
        page_id = request.POST.get("page") or None
        caisse_id = request.POST.get("caisse")
        montant = request.POST.get("montant")
        remarque = request.POST.get("remarque")

        Versement.objects.create(
            date=date,
            page_id=page_id,
            caisse_id=caisse_id,
            montant=montant,
            remarque=remarque
        )
        return redirect("versements_list")

@login_required
@admin_required
def modifier_versement(request, pk):
    versement = get_object_or_404(Versement, pk=pk)
    if versement.statut_publication == "supprimé":
        messages.warning(request, "Ce versement a été supprimé et ne peut être modifié.")
        return redirect("versements_list")
    
    if request.method == "POST":
        versement.date = request.POST.get("date")
        versement.page_id = request.POST.get("page")
        versement.caisse_id = request.POST.get("caisse")
        versement.montant = request.POST.get("montant")
        versement.remarque = request.POST.get("remarque")
        versement.save()
    return redirect("versements_list")

@login_required
@admin_required
def supprimer_versement(request, pk):
    versement = get_object_or_404(Versement, pk=pk)
    if versement.statut_publication == "supprimé":
        messages.warning(request, "Ce versement a déjà été supprimé.")
        return redirect("versements_list")

    if request.method == "POST":
        # versement.delete()
        versement.soft_delete(user=request.user)
    return redirect("versements_list")

# Mouvements de caisse
def mouvements_list(request):
    caisses = Caisse.objects.all()
    mouvements = MouvementCaisse.objects.all().order_by('-date')

    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")
    caisse = request.GET.get("caisse")

    if date_debut:
        mouvements = mouvements.filter(date__date__gte=date_debut)
    if date_fin:
        mouvements = mouvements.filter(date__date__lte=date_fin)
    if caisse:
        mouvements = mouvements.filter(Q(caisse_debit_id=caisse) | Q(caisse_credit_id=caisse))

    context = {
        "mouvements": mouvements,
        "caisses": caisses,
        "selected_caisse": caisse,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "today": now().date(),
        "is_admin": is_admin(request.user),
    }
    return render(request, "caisses/mouvements_list.html", context)

def ajouter_mouvement(request):
    if request.method == "POST":
        caisse_debit_id = request.POST["caisse_debit"]
        caisse_credit_id = request.POST["caisse_credit"]
        montant = int(request.POST["montant"])

        if caisse_debit_id == caisse_credit_id:
            messages.warning(request, "La caisse de débit et la caisse de crédit doivent être différentes.")
        else:
            solde_debit = calculer_totaux_caisses(caisse_debit_id)['solde_final']
            nouveau_solde = solde_debit - montant
            if nouveau_solde < 0:
                messages.warning(request, f"Impossible d’enregistrer : le débit ferait passer la caisse à un solde négatif ({nouveau_solde}).")
            else:
                MouvementCaisse.objects.create(
                    date=request.POST["date"],
                    caisse_debit_id=caisse_debit_id,
                    caisse_credit_id=caisse_credit_id,
                    montant=montant,
                    reference=request.POST.get("reference", "")
                )
                messages.success(request, "Mouvement enregistré.")

    return redirect("etat_caisses")

def modifier_mouvement(request, mouvement_id):
    mouvement = get_object_or_404(MouvementCaisse, id=mouvement_id)
    if mouvement.statut_publication == "supprimé":
        messages.warning(request, "Ce mouvement a été supprimé et ne peut être modifié.")
        return redirect("mouvements_list")

    if request.method == "POST":
        date_str = request.POST.get("date")
        caisse_debit_id = request.POST.get("caisse_debit")
        caisse_credit_id = request.POST.get("caisse_credit")
        montant_str = request.POST.get("montant")
        reference = request.POST.get("reference")

        if caisse_debit_id == caisse_credit_id:
            messages.error(request, "La caisse de débit et la caisse de crédit doivent être différentes.")
            return redirect("mouvements_list")

        try:
            montant = int(montant_str)
        except (ValueError, TypeError):
            messages.error(request, "Montant invalide.")
            return redirect("mouvements_list")

        # Calculer solde actuel sans ce mouvement
        solde_actuel = calculer_totaux_caisses(caisse_debit_id)['solde_final']
        # Ajuster le solde en retirant l'ancien montant du mouvement, puis en soustrayant le nouveau montant
        solde_apres_modif = solde_actuel + mouvement.montant - montant

        if solde_apres_modif < 0:
            messages.error(request, f"Impossible de modifier : le débit ferait passer la caisse à un solde négatif ({solde_apres_modif}).")
            return redirect("mouvements_list")

        try:
            mouvement.date = parse_date(date_str) if date_str else mouvement.date
            mouvement.caisse_debit_id = caisse_debit_id
            mouvement.caisse_credit_id = caisse_credit_id
            mouvement.montant = montant
            mouvement.reference = reference or ""
            mouvement.save()
            messages.success(request, "Mouvement modifié avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification : {e}")

    return redirect("mouvements_list")

def supprimer_mouvement(request, mouvement_id):
    mouvement = get_object_or_404(MouvementCaisse, id=mouvement_id)
    if mouvement.statut_publication == "supprimé":
        messages.warning(request, "Ce mouvement a déjà été supprimé.")
        return redirect("mouvements_list")
    
    # mouvement.delete()
    mouvement.soft_delete(user=request.user)
    messages.success(request, "Mouvement supprimé.")
    return redirect("mouvements_list")