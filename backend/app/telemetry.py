import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)


def setup_telemetry() -> None:
    try:
        resource = Resource.create({"service.name": "underwriting-api"})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry initialized")
    except Exception as exc:
        logger.warning("Telemetry setup skipped: %s", exc)


def get_tracer(name: str = "underwriting"):
    return trace.get_tracer(name)
