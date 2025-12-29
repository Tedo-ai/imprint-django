"""Django middleware for Imprint tracing."""

import logging

import imprint
from imprint import get_client
from imprint.context import SpanContext

from .setup import get_settings
from .db import install_query_wrapper

logger = logging.getLogger(__name__)


class ImprintMiddleware:
    """
    Django middleware that creates a root span for each request.

    Add to MIDDLEWARE in settings.py:
        MIDDLEWARE = [
            'imprint_django.middleware.ImprintMiddleware',
            ...
        ]

    The middleware should be early in the list to capture the full request.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._settings = None

    @property
    def settings(self):
        """Lazy-load settings."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def __call__(self, request):
        # Ensure DB wrapper is installed (thread-local, needs to be done per-thread)
        install_query_wrapper()

        client = get_client()

        # If Imprint not initialized or disabled, pass through
        if client is None:
            logger.debug("Imprint client is None, skipping tracing")
            return self.get_response(request)

        # Check if path should be ignored
        if client.config.should_ignore(request.path):
            logger.debug(f"Ignoring path: {request.path}")
            return self.get_response(request)

        logger.debug(f"Tracing request: {request.method} {request.path}")

        # Extract trace context from headers
        headers = {key: value for key, value in request.META.items() if key.startswith("HTTP_")}

        # Start span
        span_name = f"{request.method} {request.path}"
        ctx, span = client.start_span_from_headers(
            name=span_name,
            headers=headers,
            kind="server",
            attributes={
                "http.method": request.method,
                "http.url": request.build_absolute_uri(),
                "http.path": request.path,
                "http.scheme": request.scheme,
                "http.host": request.get_host(),
                "http.user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )

        # Store span on request for access in views
        request.imprint_span = span
        request.imprint_trace_id = span.trace_id

        # Execute request within span context
        with ctx:
            try:
                response = self.get_response(request)

                # Record response info
                span.set_status(response.status_code)
                span.set_attribute("http.status_code", response.status_code)

                if response.status_code >= 500:
                    span.record_error(message=f"HTTP {response.status_code}")

                return response

            except Exception as e:
                # Record exception
                span.record_error(e)
                span.set_status(500)
                raise

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Update span name with resolved view information."""
        span = getattr(request, "imprint_span", None)
        if span is None:
            return None

        # Get view name
        view_name = getattr(view_func, "__name__", str(view_func))
        module = getattr(view_func, "__module__", "")

        if module:
            full_name = f"{module}.{view_name}"
        else:
            full_name = view_name

        span.set_attribute("code.function", view_name)
        span.set_attribute("code.namespace", module)

        # Extract route pattern (e.g., /products/<int:pk>/ instead of /products/123/)
        route_pattern = self._extract_route_pattern(request)

        # Update span name with route pattern for better aggregation
        if route_pattern:
            span.name = f"{request.method} {route_pattern}"
            span.set_attribute("http.route", route_pattern)
        else:
            span.name = f"{request.method} {request.path}"

        return None

    def _extract_route_pattern(self, request):
        """Extract the URL route pattern from the resolved URL."""
        try:
            from django.urls import resolve

            resolved = resolve(request.path)

            # Try to get the route pattern
            if hasattr(resolved, 'route'):
                # Django 2.0+ with path() - returns clean pattern
                route = resolved.route
                # Ensure leading slash
                if route and not route.startswith('/'):
                    route = '/' + route
                return route

            # Fallback: reconstruct from regex pattern (Django 1.x or url())
            if hasattr(resolved, 'url_name') and resolved.url_name:
                # At least record the URL name
                return None

        except Exception:
            pass

        return None

    def process_exception(self, request, exception):
        """Record exception on span."""
        span = getattr(request, "imprint_span", None)
        if span:
            span.record_error(exception)
            span.set_status(500)

        # Don't suppress the exception
        return None
