from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q, Sum, F, ExpressionWrapper, IntegerField
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from common.decorators import admin_required
from common.utils import is_admin
from ventes.models import LigneCommande, Vente
from charges.models import Charge
from achats.models import Achat
from stocks.utils import calculer_total_stock
from caisses.utils import calculer_totaux_caisses
from datetime import date

@login_required
@admin_required
def rapport_vente(request):
    now = timezone.now()
    year = request.GET.get('year') 
    month = request.GET.get('month')
    # Appliquer l'année et le mois en cours uniquement si aucune valeur n'est envoyée (page chargée sans GET)
    if not request.GET:
        year = str(now.year)
        month = f"{now.month:02d}"

    page_filter = request.GET.get('page')
    article_filter = request.GET.get('article')

    lignes = LigneCommande.actifs.select_related(
        'commande__client', 'commande__page', 'article', 'commande__vente'
    ).filter(commande__vente__isnull=False)

    # Vérifie si des filtres sont soumis via GET
    filters_applied = any([year, month, page_filter, article_filter])

    # Si des filtres sont appliqués, on filtre les données
    if filters_applied:
        if year:
            lignes = lignes.filter(commande__date_livraison__year=year)
        if month:
            lignes = lignes.filter(commande__date_livraison__month=month)
        if page_filter:
            lignes = lignes.filter(commande__page__nom=page_filter)
        if article_filter:
            lignes = lignes.filter(article__nom=article_filter)
    # Si aucun filtre n'est appliqué, on ne filtre pas (toutes les données), mais on sélectionne année et mois en cours pour affichage
    selected_year = year 
    selected_month = month

    # === Regroupement total par article ===
    rapport_article = lignes.values('article__nom').annotate(
        total_qte=Sum('quantite'),
        total_montant=Sum(ExpressionWrapper(F('quantite') * F('prix_unitaire'), output_field=IntegerField())),
        total_achat=Sum(ExpressionWrapper(F('quantite') * F('article__prix_achat'), output_field=IntegerField())),
    ).annotate(
        total_marge=ExpressionWrapper(
            F('total_montant') - F('total_achat'),
            output_field=IntegerField()
        )
    )

    # === Regroupement par jour ===
    rapport_jour_raw = lignes.annotate(date=F('commande__date_livraison')).values('date').annotate(
        total_achat=Sum(F('quantite') * F('article__prix_achat'), output_field=IntegerField()),
        total_vente=Sum(F('quantite') * F('prix_unitaire'), output_field=IntegerField()),
    ).annotate(
        total_marge=F('total_vente') - F('total_achat')
    ).order_by('date')

    rapport_jour = []
    for item in rapport_jour_raw:
        date_obj = item['date']
        date_str = date_obj.strftime('%Y-%m-%d') if hasattr(date_obj, 'strftime') else str(date_obj)
        display_date = date_obj.strftime('%d/%m/%Y') if hasattr(date_obj, 'strftime') else str(date_obj)

        rapport_jour.append({
            'date': date_str,  # pour accès dans marge_par_jour_page
            'display_date': display_date,  # pour affichage
            'total_achat': item['total_achat'],
            'total_vente': item['total_vente'],
            'total_marge': item['total_marge'],
        })

        # === Regroupement par mois ===
    rapport_mois_raw = lignes.annotate(
        annee=F('commande__date_livraison__year'),
        mois=F('commande__date_livraison__month')
    ).values('annee', 'mois').annotate(
        total_achat=Sum(F('quantite') * F('article__prix_achat'), output_field=IntegerField()),
        total_vente=Sum(F('quantite') * F('prix_unitaire'), output_field=IntegerField()),
    ).annotate(
        total_marge=F('total_vente') - F('total_achat')
    ).order_by('annee', 'mois')

    rapport_mois = []
    for item in rapport_mois_raw:
        mois_str = f"{item['annee']}-{item['mois']:02d}"
        display_mois = timezone.datetime(item['annee'], item['mois'], 1).strftime('%B %Y')
        rapport_mois.append({
            'mois': mois_str,          # exemple : "2025-05"
            'display_mois': display_mois,  # exemple : "Mai 2025"
            'total_achat': item['total_achat'],
            'total_vente': item['total_vente'],
            'total_marge': item['total_marge'],
        })

    # === Pages disponibles ===
    pages_set = set()
    articles_set = set()
    for ligne in lignes:
        page = ligne.commande.page.nom if ligne.commande.page else "(Sans page)"
        pages_set.add(page)
        articles_set.add(ligne.article.nom)
    pages = sorted(pages_set)
    articles = sorted(articles_set)

    # === Calcul marge par article et page ===
    marge_par_article_page = defaultdict(lambda: defaultdict(int))
    marge_par_jour_page = defaultdict(lambda: defaultdict(int))
    marge_par_mois_page = defaultdict(lambda: defaultdict(int))

    for ligne in lignes:
        article = ligne.article.nom
        page = ligne.commande.page.nom if ligne.commande.page else "(Sans page)"
        marge = ligne.montant() - ligne.quantite * ligne.article.prix_achat
        marge_par_article_page[article][page] += marge

        date_str = ligne.commande.date_livraison.strftime("%Y-%m-%d")
        marge_par_jour_page[date_str][page] += marge

        mois_str = ligne.commande.date_livraison.strftime('%Y-%m')
        marge_par_mois_page[mois_str][page] += marge

    years = list(range(timezone.now().year, timezone.now().year - 5, -1))
    months = [(f"{i:02d}", timezone.datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]

    # === Totaux généraux ===
    total_general_qte = 0
    total_general_montant = 0
    total_general_marge = 0
    total_par_page = defaultdict(int)

    for item in rapport_article:
        total_general_qte += item['total_qte'] or 0
        total_general_montant += item['total_montant'] or 0
        total_general_marge += item['total_marge'] or 0

    for article, pages_dict in marge_par_article_page.items():
        for page, marge in pages_dict.items():
            total_par_page[page] += marge
        
    return render(request, 'statistiques/rapport_vente.html', {
        'rapport_article': rapport_article,
        'pages': pages,
        'articles': articles,
        'total_general_qte': total_general_qte,
        'total_general_montant': total_general_montant,
        'total_general_marge': total_general_marge,
        'total_par_page': total_par_page,
        'rapport_jour': rapport_jour,
        'rapport_mois': rapport_mois,
        'marge_par_article_page': marge_par_article_page,
        'marge_par_jour_page': marge_par_jour_page,
        'marge_par_mois_page': marge_par_mois_page,
        'year': selected_year,
        'month': selected_month,
        'years': years,
        'months': months,
        "is_admin": is_admin(request.user),
    })

@login_required
@admin_required
def compte_de_resultat(request):
    # 1. Chiffres d'affaires
    chiffre_affaires = Vente.actifs.aggregate(total=Sum('montant'))['total'] or 0

    # 2. Achats consommés = charges compte 60 + total des achats
    charges_60 = Charge.actifs.filter(libelle__compte_numero__startswith='60') \
        .aggregate(total=Sum('montant'))['total'] or 0

    total_achats = sum(achat.total for achat in Achat.actifs.all())

    # Stocks (depuis vue etat_stock)
    stocks_total = calculer_total_stock()

    # Variation de stock : stock final - stock initial
    # Si tu ne gères pas encore le stock initial, considère-le comme 0
    variation_stock = stocks_total  # à corriger si tu as un stock initial réel

    # Achats consommés corrigés
    achats_cons = charges_60 + total_achats - variation_stock

    # 3. Services extérieurs et autres consommations (61, 62)
    services_cons = Charge.actifs.filter(
        Q(libelle__compte_numero__startswith='61') |
        Q(libelle__compte_numero__startswith='62')
    ).aggregate(total=Sum('montant'))['total'] or 0

    # 4. Valeur ajoutée d'exploitation
    valeur_ajoutee = chiffre_affaires - achats_cons - services_cons

    # 5. Charges de personnel (64)
    charges_personnel = Charge.actifs.filter(libelle__compte_numero__startswith='64') \
        .aggregate(total=Sum('montant'))['total'] or 0

    # 6. Impôts et taxes (63)
    taxes = Charge.actifs.filter(libelle__compte_numero__startswith='63') \
        .aggregate(total=Sum('montant'))['total'] or 0

    # 7. Excédent Brut d'Exploitation
    ebe = valeur_ajoutee - charges_personnel - taxes

    # 8. Autres charges opérationnelles (65)
    autres_charges = Charge.actifs.filter(libelle__compte_numero__startswith='65') \
        .aggregate(total=Sum('montant'))['total'] or 0

    # 9. Dotations aux amortissements et provisions (68)
    dotations = Charge.actifs.filter(libelle__compte_numero__startswith='68') \
        .aggregate(total=Sum('montant'))['total'] or 0

    # 10. Résultat opérationnel
    resultat_op = ebe - autres_charges - dotations

    contexte = {
        "compte_resultat": [
            {"num": 1, "rubrique": "Chiffres d'affaires", "montant": chiffre_affaires},
            {"num": 2, "rubrique": "Achats consommés", "montant": achats_cons},
            {"num": 3, "rubrique": "Services extérieurs et autres consommations", "montant": services_cons or "-"},
            {"num": 4, "rubrique": "Valeur ajoutée d'exploitation", "montant": valeur_ajoutee, "is_total": True},
            {"num": 5, "rubrique": "Charges de personnel", "montant": charges_personnel},
            {"num": 6, "rubrique": "Impôts, taxes et versements assimilés", "montant": taxes},
            {"num": 7, "rubrique": "Excédent Brut d'Exploitation", "montant": ebe, "is_total": True},
            {"num": 8, "rubrique": "Autres charges opérationnelles", "montant": autres_charges or "-"},
            {"num": 9, "rubrique": "Dotations aux amortissements, aux provisions et pertes de valeurs", "montant": dotations or "-"},
            {"num": 10, "rubrique": "Résultat opérationnel", "montant": resultat_op, "is_total": True},
        ]
    }
    return render(request, 'statistiques/compte_de_resultat.html', contexte)

@login_required
@admin_required
def bilan(request):
    # Capital (charges avec compte_numero commençant par 1)
    capital = Charge.actifs.filter(libelle__compte_numero__startswith='1') \
        .aggregate(total=Sum('montant'))['total'] or 0

    # Immobilisations (charges avec compte_numero commençant par 2)
    immobilisations = Charge.actifs.filter(libelle__compte_numero__startswith='2') \
        .aggregate(total=Sum('montant'))['total'] or 0

    # Stocks (depuis vue etat_stock)
    stocks_total = calculer_total_stock()

    # Trésorerie et versements
    totaux_caisses = calculer_totaux_caisses()
    solde_final = totaux_caisses['solde_final']
    total_versements = totaux_caisses['versements']

    # Résultat opérationnel (repris de compte_de_resultat)
    chiffre_affaires = Vente.actifs.aggregate(total=Sum('montant'))['total'] or 0
    charges_60 = Charge.actifs.filter(libelle__compte_numero__startswith='60') \
        .aggregate(total=Sum('montant'))['total'] or 0
    total_achats = sum(achat.total for achat in Achat.actifs.all())

    # Variation de stock : stock final - stock initial
    # Si tu ne gères pas encore le stock initial, considère-le comme 0
    variation_stock = stocks_total  # à corriger si tu as un stock initial réel

    # Achats consommés corrigés
    achats_cons = charges_60 + total_achats - variation_stock

    services_cons = Charge.actifs.filter(
        Q(libelle__compte_numero__startswith='61') |
        Q(libelle__compte_numero__startswith='62')
    ).aggregate(total=Sum('montant'))['total'] or 0
    valeur_ajoutee = chiffre_affaires - achats_cons - services_cons

    charges_personnel = Charge.actifs.filter(libelle__compte_numero__startswith='64') \
        .aggregate(total=Sum('montant'))['total'] or 0
    taxes = Charge.actifs.filter(libelle__compte_numero__startswith='63') \
        .aggregate(total=Sum('montant'))['total'] or 0
    ebe = valeur_ajoutee - charges_personnel - taxes

    autres_charges = Charge.actifs.filter(libelle__compte_numero__startswith='65') \
        .aggregate(total=Sum('montant'))['total'] or 0
    dotations = Charge.actifs.filter(libelle__compte_numero__startswith='68') \
        .aggregate(total=Sum('montant'))['total'] or 0

    resultat_op = ebe - autres_charges - dotations

    # Total actif
    total_actif = immobilisations + stocks_total + solde_final + total_versements

    # Total passif = Capital + Résultat de l'exercice
    total_passif = capital + resultat_op

    context = {
        "immobilisations": immobilisations,
        "stocks": stocks_total,
        "tresorerie": solde_final,
        "versements": total_versements,
        "capital": capital,
        "resultat": resultat_op,
        "total_actif": total_actif,
        "total_passif": total_passif,
        "today": date.today(),
        "is_admin": is_admin(request.user),
    }

    return render(request, 'statistiques/bilan.html', context)
