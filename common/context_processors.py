# common/context_processors.py

def is_admin_context(request):
    is_admin = (
        request.user.is_authenticated
        and getattr(request.user.role, "role", "") == "Admin"
    )
    return {"is_admin": is_admin}
