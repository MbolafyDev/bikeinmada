import threading

_user = threading.local()

def get_current_user():
    return getattr(_user, 'value', None)

class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # print(f"[MIDDLEWARE] Utilisateur dans la requête : {request.user}")
        try:
            _user.value = request.user if request.user.is_authenticated else None
            response = self.get_response(request)
        finally:
            _user.value = None  # Nettoyage important !
        return response
