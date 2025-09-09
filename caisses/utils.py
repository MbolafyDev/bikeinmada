# caisses/utils.py
from django.db.models import Sum
from .models import Caisse, MouvementCaisse
from ventes.models import Vente
from achats.models import Achat
from charges.models import Charge
from caisses.models import Versement


def calculer_totaux_caisses(caisse_id=None):
    if caisse_id:
        caisses = Caisse.objects.filter(id=caisse_id)
    else:
        caisses = Caisse.objects.all()

    total_solde_final = 0
    total_versements = 0

    for caisse in caisses:
        ventes_total = Vente.actifs.filter(paiement=caisse).aggregate(total=Sum('montant'))['total'] or 0
        achats_total = Achat.actifs.filter(paiement=caisse).aggregate(total=Sum('lignes_achats__montant'))['total'] or 0
        charges_total = Charge.actifs.filter(
            paiement=caisse,
            libelle__compte_numero__startswith="6"
        ).aggregate(total=Sum('montant'))['total'] or 0
        versements_total = Versement.actifs.filter(caisse=caisse).aggregate(total=Sum('montant'))['total'] or 0

        mouvements_entree = MouvementCaisse.actifs.filter(
            caisse_credit_id=caisse.id
        ).aggregate(total=Sum('montant'))['total'] or 0

        mouvements_sortie = MouvementCaisse.actifs.filter(
            caisse_debit_id=caisse.id
        ).aggregate(total=Sum('montant'))['total'] or 0

        entrees = ventes_total + mouvements_entree
        sorties = achats_total + charges_total + versements_total + mouvements_sortie
        solde_final = caisse.solde_initial + entrees - sorties

        total_solde_final += solde_final
        total_versements += versements_total

    return {
        'solde_final': total_solde_final,
        'versements': total_versements,
    }
