from .env_base_dir import BASE_DIR
from pathlib import Path
import os

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-secret-key')

AUTH_USER_MODEL = 'users.CustomUser'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.humanize',
    'django.contrib.staticfiles',

    # apps
    'users',
    'articles',
    'achats',
    'ventes',
    'clients',
    'livraison',
    'stocks',
    'common',
    'charges',
    'caisses',
    'statistiques',
    'service',
    'pwa',
    'configuration',
    'dashboard'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'common.middleware.CurrentUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

]

ROOT_URLCONF = 'bikeinmada.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'common.context_processors.is_admin_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'bikeinmada.wsgi.application'
ASGI_APPLICATION = "bikeinmada.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr'
TIME_ZONE = 'Indian/Antananarivo'
USE_TZ = True
USE_I18N = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = "/users/login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

APPEND_SLASH = True

APP_VERSION = "2025-09-17.1"