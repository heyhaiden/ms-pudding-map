"""Dedicated OpenTelemetry log export for the stock polling CLI."""

import atexit
import logging
import os
import sys

_initialized = False
_logger = logging.getLogger("ms_pudding_map.posthog")


def _configuration_error(variable):
    return (
        f"{variable} variable required by PostHog is missing or un-configured, this causes events to be silently "
        f"missed. This error stops appearing once {variable} is configured"
    )


def get_posthog_logger():
    """Return the dedicated PostHog logger, or None when log export is unconfigured."""
    global _initialized

    if _initialized:
        return _logger if _logger.handlers else None
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

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    logger_provider = LoggerProvider(resource=Resource.create({"service.name": "ms-pudding-map-poller"}))
    set_logger_provider(logger_provider)
    exporter = OTLPLogExporter(
        endpoint=f"{host.rstrip('/')}/i/v1/logs",
        headers={"Authorization": f"Bearer {project_token}"},
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    _logger.addHandler(LoggingHandler(logger_provider=logger_provider))
    atexit.register(logger_provider.shutdown)
    return _logger
