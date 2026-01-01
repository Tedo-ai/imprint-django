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
        'TRACE_DB': True,     # Trace database queries (default: True)
        'TRACE_JOBS': True,   # Trace Django-Q jobs (default: True)
    }

    # For manual job tracing:
    from imprint_django.jobs import traced_task

    @traced_task
    def my_background_task():
        pass
"""

__version__ = "0.1.0"

default_app_config = "imprint_django.apps.ImprintConfig"

# Export traced_task for convenience
try:
    from .jobs import traced_task
except ImportError:
    traced_task = None
