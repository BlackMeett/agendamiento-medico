"""Configuración para publicar la demo por un túnel HTTPS.

Se activa solo cuando DJANGO_SETTINGS_MODULE=config.settings_public.
No modifica la configuración local (config.settings).
"""
from .settings import *  # noqa: F401,F403

DEBUG = False

# El túnel reenvía el dominio público, que cambia en cada arranque.
ALLOWED_HOSTS = ["*"]

# La URL gratuita de Cloudflare cambia en cada arranque. Sin esta lista,
# Django muestra el login pero rechaza el POST con error CSRF 403.
CSRF_TRUSTED_ORIGINS = ["https://*.trycloudflare.com"]

# cloudflared termina el TLS y reenvía por HTTP con esta cabecera.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Los estáticos los sirve WhiteNoise (producción), no runserver.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# STATIC_URL original es relativo ("static/"), lo que rompe el CSS en rutas
# anidadas como /cuenta/login/.
STATIC_URL = "/static/"
