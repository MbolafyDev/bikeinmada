# common/context_processors.py

def is_admin_context(request):
    is_admin = (
        request.user.is_authenticated
        and getattr(request.user.role, "role", "") == "Admin"
    )
    return {"is_admin": is_admin}

def has_admin_role(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    role = getattr(user, "role", None)
    label = getattr(role, "role", "") if role else ""
    return label.strip().lower() in {"admin", "administrateur", "superadmin"}


def config_nav_flags(request):
    """
    Expose can_manage_admin_things pour tous les templates.
    """
    try:
        user = request.user
    except Exception:
        user = None
    return {
        "can_manage_admin_things": has_admin_role(user),
    }
