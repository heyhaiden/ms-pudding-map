"""Process-wide PostHog client for the polling CLI."""

import atexit
import os
import sys

_posthog_client = None
_initialized = False


def _configuration_error(variable):
    return (
        f"{variable} variable required by PostHog is missing or un-configured, this causes events to be silently "
        f"missed. This error stops appearing once {variable} is configured"
    )


def get_posthog_client():
    """Return the process-wide PostHog client, or None when analytics is unconfigured."""
    global _initialized, _posthog_client

    if _initialized:
        return _posthog_client
    _initialized = True

    project_token = os.getenv("POSTHOG_PROJECT_TOKEN", "").strip()
    host = os.getenv("POSTHOG_HOST", "").strip()
    missing_variable = "POSTHOG_PROJECT_TOKEN" if not project_token else "POSTHOG_HOST" if not host else None
    if missing_variable:
        message = _configuration_error(missing_variable)
        if os.getenv("POSTHOG_DEBUG", "").lower() in {"1", "true", "yes"}:
            raise RuntimeError(message)
        print(f"warning: {message}", file=sys.stderr)
        return None

    from posthog import Posthog

    _posthog_client = Posthog(
        project_token,
        host=host,
        enable_exception_autocapture=True,
    )
    atexit.register(_posthog_client.shutdown)
    return _posthog_client
