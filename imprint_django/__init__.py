"""
Imprint Django integration for distributed tracing.

Usage:
    # settings.py
    INSTALLED_APPS = [
        ...
        'imprint_django',
    ]

    MIDDLEWARE = [
        'imprint_django.middleware.ImprintMiddleware',
        ...
    ]

    IMPRINT = {
        'API_KEY': 'imp_live_...',
        'SERVICE_NAME': 'my-django-app',
    }
"""

__version__ = "0.1.0"

default_app_config = "imprint_django.apps.ImprintConfig"
