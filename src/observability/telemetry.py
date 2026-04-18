# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""OpenTelemetry integration for orchestrator observability.

Provides TelemetryManager which wraps OTel span creation with a no-op
fallback when observability is disabled. This module has zero overhead
when disabled and no hard dependency on opentelemetry packages.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


class NoOpSpan:
    """Span that records nothing. Used when observability is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def is_recording(self) -> bool:
        return False


class TelemetryManager:
    """Manages OpenTelemetry tracing for orchestrator execution.

    When observability.enabled=false (the default), all span creation
    returns NoOpSpan instances with zero overhead. When enabled, spans
    are emitted via the configured OTLP gRPC exporter.

    Attributes:
        enabled: Whether OTel tracing is active.
        service_name: Service name for OTel resource.
        endpoint: OTLP gRPC endpoint.

    """

    def __init__(self) -> None:
        self._enabled = False
        self._tracer: Any = None
        self._provider: Any = None
        self.service_name: str = "plico"
        self.endpoint: str = "http://localhost:4317"
        self._insecure: bool = True

        self._try_initialize()

    def _try_initialize(self) -> None:
        """Attempt to initialize OTel from config. Fails silently if disabled or missing."""
        try:
            from ..config import get_config

            config = get_config()
            obs_config = config.observability

            if not obs_config.enabled:
                logger.debug("Observability disabled in config")
                return

            self.service_name = obs_config.otel.service_name
            self.endpoint = obs_config.otel.endpoint
            self._insecure = obs_config.otel.insecure
            self._enabled = True
            self._setup_tracer()
            logger.info(f"Telemetry enabled: service={self.service_name}, endpoint={self.endpoint}")
        except Exception as e:
            logger.debug(f"Telemetry initialization skipped: {e}")
            self._enabled = False

    def _setup_tracer(self) -> None:
        """Set up the OTel tracer provider and exporter."""
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": self.service_name})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=self.endpoint, insecure=self._insecure)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)

            self._tracer = trace.get_tracer("plico.orchestrator")
            self._provider = provider
        except ImportError:
            logger.warning(
                "OpenTelemetry packages not installed. Install with: pip install ffclients[otel]"
            )
            self._enabled = False
        except Exception as e:
            logger.warning(f"Failed to setup OTel tracer: {e}")
            self._enabled = False

    @property
    def enabled(self) -> bool:
        """Whether OTel tracing is active."""
        return self._enabled

    @contextmanager
    def span(self, name: str) -> Generator[NoOpSpan, None, None]:
        """Create a traced span. Returns NoOpSpan when disabled.

        Args:
            name: Span name (e.g., "orchestrator.run").

        Yields:
            A span object with set_attribute() and record_exception().

        """
        if not self._enabled or self._tracer is None:
            yield NoOpSpan()
            return

        with self._tracer.start_as_current_span(name) as otel_span:
            yield otel_span

    def shutdown(self) -> None:
        """Flush and shutdown the tracer provider."""
        if self._provider is not None:
            try:
                self._provider.shutdown()
                logger.debug("Telemetry provider shut down")
            except Exception as e:
                logger.debug(f"Error shutting down telemetry: {e}")


_manager: TelemetryManager | None = None


def get_telemetry_manager() -> TelemetryManager:
    """Get the global TelemetryManager instance.

    Creates on first call. Returns cached instance on subsequent calls.
    Call reload_telemetry() after config changes.

    Returns:
        The global TelemetryManager.

    """
    global _manager
    if _manager is None:
        _manager = TelemetryManager()
    return _manager


def reload_telemetry() -> TelemetryManager:
    """Shutdown existing manager and create a fresh one.

    Use after changing observability config at runtime.

    Returns:
        A new TelemetryManager.

    """
    global _manager
    if _manager is not None:
        _manager.shutdown()
    _manager = TelemetryManager()
    return _manager


def reset_telemetry() -> None:
    """Reset the global TelemetryManager singleton.

    Shuts down any active provider and sets the singleton to None.
    Intended for test teardown to prevent cross-test pollution.
    """
    global _manager
    if _manager is not None:
        _manager.shutdown()
    _manager = None
