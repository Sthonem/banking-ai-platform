from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from banking_common.config import get_settings
from banking_common.logging import CorrelationIdMiddleware


def configure_observability(app: FastAPI, service_name: str) -> None:
    app.add_middleware(CorrelationIdMiddleware)
    Instrumentator().instrument(app).expose(app)

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(ZipkinExporter(endpoint=get_settings().zipkin_endpoint)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
