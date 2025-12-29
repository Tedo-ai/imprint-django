"""Setup Imprint from Django settings."""

import imprint
from imprint import Config


def get_settings():
    """Get Imprint settings from Django settings."""
    from django.conf import settings

    return getattr(settings, "IMPRINT", {})


def setup_imprint():
    """Initialize Imprint with Django settings."""
    settings = get_settings()

    if not settings.get("ENABLED", True):
        return

    config = Config(
        api_key=settings.get("API_KEY", ""),
        service_name=settings.get("SERVICE_NAME", "django-app"),
        ingest_url=settings.get("INGEST_URL", "http://localhost:17080/v1/spans"),
        ignore_paths=settings.get("IGNORE_PATHS", []),
        ignore_prefixes=settings.get("IGNORE_PREFIXES", ["/static/", "/media/"]),
        ignore_extensions=settings.get("IGNORE_EXTENSIONS", Config.ignore_extensions),
        batch_size=settings.get("BATCH_SIZE", 100),
        flush_interval=settings.get("FLUSH_INTERVAL", 5.0),
        buffer_size=settings.get("BUFFER_SIZE", 1000),
        sampling_rate=settings.get("SAMPLING_RATE", 1.0),
        debug=settings.get("DEBUG", False),
        enabled=settings.get("ENABLED", True),
    )

    imprint.init(config=config)
