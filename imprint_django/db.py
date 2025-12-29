"""Database query instrumentation for Django."""

import logging
from contextlib import contextmanager

from django.db import connection

import imprint
from imprint import get_client

logger = logging.getLogger(__name__)

# Maximum SQL length to store
MAX_SQL_LENGTH = 2048


class QueryWrapper:
    """Wrapper that creates spans for database queries."""

    def __call__(self, execute, sql, params, many, context):
        client = get_client()
        if client is None:
            return execute(sql, params, many, context)

        # Get database info
        db_alias = context["connection"].alias
        db_vendor = context["connection"].vendor  # 'postgresql', 'mysql', 'sqlite'

        # Truncate SQL if too long
        sql_display = sql[:MAX_SQL_LENGTH] + "..." if len(sql) > MAX_SQL_LENGTH else sql

        # Create child span
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


_wrapper_installed = False


def install_query_wrapper():
    """Install the query wrapper to instrument all database queries."""
    global _wrapper_installed
    if _wrapper_installed:
        return

    wrapper = QueryWrapper()
    connection.execute_wrappers.append(wrapper)
    _wrapper_installed = True
    logger.debug("Imprint database instrumentation installed")


def uninstall_query_wrapper():
    """Remove the query wrapper."""
    global _wrapper_installed
    # Find and remove our wrapper
    connection.execute_wrappers = [
        w for w in connection.execute_wrappers
        if not isinstance(w, QueryWrapper)
    ]
    _wrapper_installed = False
