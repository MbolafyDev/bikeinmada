from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from common.utils import is_admin

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            if not request.user.is_authenticated:
                return redirect('login')  # ou une autre vue de connexion
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper
