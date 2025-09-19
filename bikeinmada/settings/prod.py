from .env_base_dir import BASE_DIR
from .base import *
import os

DEBUG = False

ALLOWED_HOSTS = ['bikeinmada1.pythonanywhere.com']

# --- Base de données (MySQL PA) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', ''),
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', ''),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES', NAMES 'utf8mb4'",
        },
        'CONN_MAX_AGE': 60,
    }
}

# --- Email ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# --- Sécurité HTTPS (prod uniquement) ---
SECURE_SSL_REDIRECT = True                  # force http -> https
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS (recommandé)
SECURE_HSTS_SECONDS = 31536000              # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = False      # passe à True si tous tes sous-domaines sont HTTPS
SECURE_HSTS_PRELOAD = False

# Derrière le proxy PA
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CSRF
CSRF_TRUSTED_ORIGINS = ["https://bikeinmada1.pythonanywhere.com"]

# (Optionnel mais conseillé)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
REFERRER_POLICY = "strict-origin-when-cross-origin"
