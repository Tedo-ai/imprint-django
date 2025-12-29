# Imprint Django

Django integration for distributed tracing with Imprint.

## Installation

```bash
pip install imprint-django
```

## Usage

1. Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'imprint_django',
]
```

2. Add middleware (early in the list):

```python
MIDDLEWARE = [
    'imprint_django.middleware.ImprintMiddleware',
    'django.middleware.security.SecurityMiddleware',
    ...
]
```

3. Configure in settings:

```python
IMPRINT = {
    'API_KEY': 'imp_live_...',
    'SERVICE_NAME': 'my-django-app',
    'INGEST_URL': 'http://localhost:17080/v1/spans',
}
```

## Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `API_KEY` | `""` | Imprint API key (required) |
| `SERVICE_NAME` | `"django-app"` | Service name for spans |
| `INGEST_URL` | `"http://localhost:17080/v1/spans"` | Ingest endpoint |
| `ENABLED` | `True` | Enable/disable tracing |
| `DEBUG` | `False` | Enable debug logging |
| `SAMPLING_RATE` | `1.0` | Sampling rate (0.0 to 1.0) |
| `IGNORE_PATHS` | `[]` | Exact paths to ignore |
| `IGNORE_PREFIXES` | `["/static/", "/media/"]` | Path prefixes to ignore |
| `IGNORE_EXTENSIONS` | `[".css", ".js", ...]` | File extensions to ignore |
| `BATCH_SIZE` | `100` | Spans per batch |
| `FLUSH_INTERVAL` | `5.0` | Flush interval in seconds |

## Accessing Trace Context

In views, you can access the current span:

```python
def my_view(request):
    span = request.imprint_span
    span.set_attribute("custom.key", "value")

    # Get trace ID for logging
    trace_id = request.imprint_trace_id

    return HttpResponse("OK")
```

## Manual Spans

Create child spans for sub-operations:

```python
import imprint

def my_view(request):
    # This creates a child of the request span
    with imprint.start_span("database_query") as span:
        span.set_attribute("db.statement", "SELECT ...")
        # ... do query ...

    return HttpResponse("OK")
```
