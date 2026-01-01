"""
Django-Q2 job tracing integration.

Automatically traces background jobs run via django-q2.

Usage:
    # In your Django settings, ensure imprint_django is in INSTALLED_APPS
    # The integration is automatic via Django-Q signals.

    # Or manually trace a function:
    from imprint_django.jobs import traced_task

    @traced_task
    def my_task(arg1, arg2):
        return result
"""
import logging
import functools
import time
from typing import Callable, Any

logger = logging.getLogger(__name__)


def setup_django_q_tracing():
    """
    Set up automatic tracing for Django-Q tasks via signals.

    This hooks into Django-Q's post_execute signal to create spans
    for all background tasks after they complete.

    Note: Django-Q runs pre_execute and post_execute in different processes,
    so we create the complete span in post_execute using task timing data.
    """
    try:
        from django_q.signals import post_execute
        from imprint import get_client

        def on_post_execute(sender, task, **kwargs):
            """Called after a task executes - creates the job span."""
            try:
                task_id = task.get('id', 'unknown')

                # Re-initialize Imprint client in worker process if needed
                client = get_client()
                if client is None or not client._worker_thread.is_alive():
                    from .setup import setup_imprint
                    setup_imprint()
                    client = get_client()

                if client is None:
                    logger.debug(f"[IMPRINT] No client available, skipping job tracing for task {task_id}")
                    return

                # Get task info
                func = task.get('func')
                task_name = task.get('name') or (func if isinstance(func, str) else getattr(func, '__name__', str(func)))
                func_path = func if isinstance(func, str) else f"{getattr(func, '__module__', 'unknown')}.{getattr(func, '__name__', str(func))}"

                # Check if task succeeded or failed
                success = task.get('success', False)
                result = task.get('result')

                # Use Ruby SDK format: "TaskName#perform"
                span_name = f"{task_name}#perform"

                # Get timing - Django-Q provides 'started' and 'stopped' timestamps
                started = task.get('started')
                stopped = task.get('stopped')

                # Calculate start_time in nanoseconds
                if started:
                    # Django-Q stores timestamps as datetime objects
                    start_time_ns = int(started.timestamp() * 1_000_000_000)
                else:
                    start_time_ns = None

                # Create the span with explicit start time
                ctx, span = client.start_span(
                    name=span_name,
                    kind="consumer",
                    attributes={
                        "messaging.system": "django_q",
                        "messaging.destination": task.get('group', 'default'),
                        "django_q.task_id": task_id,
                        "django_q.task_name": task_name,
                        "django_q.func": func_path,
                    },
                    start_time=start_time_ns,
                )

                # Set status and result
                if success:
                    span.set_status(200)
                    if result is not None:
                        result_str = str(result)
                        if len(result_str) <= 1000:
                            span.set_attribute("django_q.result", result_str)
                else:
                    span.set_status(500)
                    span.record_error(message=str(result) if result else "Task failed")

                # End the span with explicit end time
                if stopped:
                    end_time_ns = int(stopped.timestamp() * 1_000_000_000)
                    span.end(end_time_ns=end_time_ns)
                else:
                    span.end()

                logger.info(f"[IMPRINT] Recorded job span: {span_name} (trace_id={span.trace_id}, success={success})")

            except Exception as e:
                logger.error(f"[IMPRINT] post_execute ERROR: {e}", exc_info=True)

        # Connect signal
        post_execute.connect(on_post_execute)

        logger.info("Django-Q tracing enabled")

    except ImportError:
        logger.debug("django-q not installed, skipping job tracing setup")
    except Exception as e:
        logger.warning(f"Failed to set up Django-Q tracing: {e}")


def traced_task(func: Callable = None, *, name: str = None) -> Callable:
    """
    Decorator to trace a task function.

    Can be used with or without arguments:

        @traced_task
        def my_task():
            pass

        @traced_task(name="custom-name")
        def my_other_task():
            pass
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            from imprint import get_client

            client = get_client()
            if client is None:
                return fn(*args, **kwargs)

            task_name = name or fn.__name__
            func_path = f"{fn.__module__}.{fn.__name__}"

            # Use Ruby SDK format: "TaskName#perform"
            span_name = f"{task_name}#perform"

            ctx, span = client.start_span(
                name=span_name,
                kind="consumer",
                attributes={
                    "messaging.system": "manual",
                    "django_q.task_name": task_name,
                    "django_q.func": func_path,
                },
            )

            with ctx:
                try:
                    result = fn(*args, **kwargs)
                    span.set_status(200)
                    return result
                except Exception as e:
                    span.record_error(e)
                    span.set_status(500)
                    raise

        return wrapper

    if func is not None:
        # Called without arguments: @traced_task
        return decorator(func)

    # Called with arguments: @traced_task(name="...")
    return decorator
