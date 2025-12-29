"""Django app configuration for Imprint."""

from django.apps import AppConfig


class ImprintConfig(AppConfig):
    """Django app config that initializes Imprint on startup."""

    name = "imprint_django"
    verbose_name = "Imprint Tracing"

    def ready(self):
        """Initialize Imprint when Django starts."""
        from .setup import setup_imprint
        setup_imprint()
