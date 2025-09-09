from articles.models import Article
from achats.models import LigneAchat
from ventes.models import LigneCommande
from .models import Inventaire
from django.db.models import Sum, Q

def calculer_stock_article(article):
    entrees = (
        LigneAchat.objects.filter(
            achat__statut_publication__iexact="publié",
            article=article
        )
        .aggregate(total=Sum("quantite"))["total"] or 0
    )

    sorties = (
        LigneCommande.objects.filter(
            commande__statut_publication__iexact="publié",
            # On EXCLUT les ventes non comptabilisées
        )
        .exclude(commande__statut_vente__in=["Supprimée", "Annulée", "Reportée"])
        .filter(article=article)
        .aggregate(total=Sum("quantite"))["total"] or 0
    )

    ajustements = (
        Inventaire.objects.filter(
            statut_publication__iexact="publié",
            article=article
        )
        .aggregate(total=Sum("ajustement"))["total"] or 0
    )

    return entrees - sorties + ajustements

def calculer_total_stock():
    total_valeur = 0
    articles = Article.objects.all()

    for article in articles:
        stock = calculer_stock_article(article)
        valeur = stock * article.prix_achat if stock > 0 else 0
        total_valeur += valeur

    return total_valeur
