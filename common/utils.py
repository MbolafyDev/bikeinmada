# zarastore/common/utils.py

def is_admin(user):
    return user.is_authenticated and getattr(user.role, "role", "") == "Admin"

DISPLAY_CHOICES = ("table", "cards")

def resolve_display_mode(request, session_key="display_mode", default="cards"):
    """
    Détermine le mode d’affichage (table/cards) selon l’ordre de priorité :
    1) Paramètre GET ?display=...
    2) Session (clé = session_key)
    3) Valeur par défaut (cards)

    Sauvegarde dans la session si passé en GET.
    """
    display = request.GET.get("display")
    if display in DISPLAY_CHOICES:
        request.session[session_key] = display
    else:
        display = request.session.get(session_key, default)
    return display
