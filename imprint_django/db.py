"""Database query instrumentation for Django."""

import logging
from contextvars import ContextVar

from django.db import connection
from imprint import get_client

logger = logging.getLogger(__name__)

# Maximum SQL length to store
MAX_SQL_LENGTH = 2048

# Context variable to disable DB tracing (e.g., during bulk job operations)
_db_tracing_disabled: ContextVar[bool] = ContextVar("db_tracing_disabled", default=False)


def disable_db_tracing():
    """Disable DB query tracing in the current context."""
    _db_tracing_disabled.set(True)


def enable_db_tracing():
    """Re-enable DB query tracing in the current context."""
    _db_tracing_disabled.set(False)


def is_db_tracing_disabled() -> bool:
    """Check if DB tracing is disabled in the current context."""
    return _db_tracing_disabled.get()

# Internal queries to skip (Django ORM introspection, schema queries, etc.)
SKIP_SQL_PREFIXES = (
    "SAVEPOINT ",
    "RELEASE SAVEPOINT ",
    "SET ",
    "SHOW ",
    "SELECT version()",
    "SELECT VERSION()",
    # Django schema introspection
    "SELECT c.relname",
    "SELECT t.typname",
    "SELECT pg_catalog.",
    "SELECT information_schema.",
    # SQLite introspection
    "SELECT sqlite_version()",
    "SELECT name FROM sqlite_master",
    "PRAGMA ",
)


def _should_skip_query(sql: str) -> bool:
    """Check if this query should be skipped (internal/schema queries)."""
    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()

    # Skip based on prefix
    for prefix in SKIP_SQL_PREFIXES:
        if sql_upper.startswith(prefix.upper()):
            return True

    # Skip EXPLAIN queries
    if sql_upper.startswith("EXPLAIN"):
        return True

    return False


class QueryWrapper:
    """Wrapper that creates spans for database queries."""

    def __call__(self, execute, sql, params, many, context):
        from imprint.context import get_current_span

        client = get_client()
        if client is None:
            return execute(sql, params, many, context)

        # Skip if DB tracing is explicitly disabled (e.g., during bulk jobs)
        if is_db_tracing_disabled():
            return execute(sql, params, many, context)

        # Skip internal/schema queries
        if _should_skip_query(sql):
            return execute(sql, params, many, context)

        # Check if we have a parent span - if not, skip tracing this query
        # to avoid orphan DB spans showing as root traces
        parent_span = get_current_span()
        if parent_span is None:
            return execute(sql, params, many, context)

        # Get database info
        db_alias = context["connection"].alias
        db_vendor = context["connection"].vendor  # 'postgresql', 'mysql', 'sqlite'

        # Truncate SQL if too long
        sql_display = sql[:MAX_SQL_LENGTH] + "..." if len(sql) > MAX_SQL_LENGTH else sql

        # Create child span (will inherit from parent via get_current_span)
        ctx, span = client.start_span(
            name=f"DB {_get_operation(sql)}",
            kind="client",
            attributes={
                "db.system": db_vendor,
                "db.name": db_alias,
                "db.statement": sql_display,
            },
        )

        with ctx:
            try:
                result = execute(sql, params, many, context)
                span.set_status(200)
                return result
            except Exception as e:
                span.record_error(e)
                span.set_status(500)
                raise


def _get_operation(sql: str) -> str:
    """Extract the SQL operation (SELECT, INSERT, UPDATE, DELETE, etc.)."""
    sql_upper = sql.strip().upper()
    for op in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "BEGIN", "COMMIT", "ROLLBACK"]:
        if sql_upper.startswith(op):
            return op
    return "QUERY"


def install_query_wrapper():
    """Install the query wrapper to instrument all database queries."""
    # Check if already installed (connection.execute_wrappers is thread-local)
    for wrapper in connection.execute_wrappers:
        if isinstance(wrapper, QueryWrapper):
            return

    wrapper = QueryWrapper()
    connection.execute_wrappers.append(wrapper)
    logger.debug("Imprint database instrumentation installed")


def uninstall_query_wrapper():
    """Remove the query wrapper."""
    # Find and remove our wrapper
    connection.execute_wrappers = [
        w for w in connection.execute_wrappers
        if not isinstance(w, QueryWrapper)
    ]
