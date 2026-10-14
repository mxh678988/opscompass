"""OpenTelemetry 可观测性配置与初始化。

- 默认关闭（OTEL_ENABLED=False），通过 .env 开启。
- 支持 OTLP gRPC/HTTP 导出器，默认 gRPC。
- 自动为 FastAPI 和 SQLAlchemy 注入 Instrumentor。
"""

import logging

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import settings

logger = logging.getLogger(__name__)


def init_tracing() -> TracerProvider | None:
    """初始化 TracerProvider，返回 provider 实例；未开启时返回 None。"""
    if not settings.OTEL_ENABLED:
        logger.info("[OTel] 已关闭（OTEL_ENABLED=False），跳过 tracing 初始化")
        return None

    resource = Resource.create({
        "service.name": settings.OTEL_SERVICE_NAME,
        "service.version": settings.APP_VERSION,
        "deployment.environment": settings.ENV,
    })

    provider = TracerProvider(resource=resource)

    # OTLP 导出器
    try:
        if settings.OTEL_EXPORTER_OTLP_PROTOCOL == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(
                endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True
            )
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)

        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info(
            "[OTel] OTLP %s 导出器已注册 -> %s",
            settings.OTEL_EXPORTER_OTLP_PROTOCOL,
            settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        )
    except Exception as exc:
        logger.warning("[OTel] OTLP 导出器注册失败，降级为 Console 导出: %s", exc)
        # 降级：Console 导出器
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    logger.info("[OTel] TracerProvider 已初始化: %s", settings.OTEL_SERVICE_NAME)
    return provider


def instrument_app(app=None):
    """注入 FastAPI / SQLAlchemy Instrumentor。"""
    if not settings.OTEL_ENABLED:
        return

    # FastAPI Instrumentor
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("[OTel] FastAPI Instrumentor 已注入")

    # SQLAlchemy Instrumentor
    try:
        SQLAlchemyInstrumentor().instrument()
        logger.info("[OTel] SQLAlchemy Instrumentor 已注入")
    except Exception as exc:
        logger.warning("[OTel] SQLAlchemy Instrumentor 注入失败: %s", exc)
