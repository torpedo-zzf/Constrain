from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class BusBackend(str, Enum):
    MEMORY = "memory"
    RABBITMQ = "rabbitmq"
    REDIS_PUBSUB = "redis_pubsub"


class StoreBackend(str, Enum):
    MEMORY = "memory"
    SQLITE = "sqlite"
    POSTGRES = "postgres"


class TracingMode(str, Enum):
    DEV = "dev"
    PRODUCTION = "production"


class HarnessConfig(BaseModel):
    """Top-level configuration for the Harness.

    Loaded from YAML/JSON with environment variable override support.
    """

    mode: str = "memory"
    bus_backend: BusBackend = BusBackend.MEMORY
    state_store_backend: StoreBackend = StoreBackend.MEMORY

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql://user:pass@localhost:5432/constrain"

    l2_confidence_threshold: float = 0.8

    skill_paths: list[str] = Field(default_factory=lambda: ["skills"])
    tracing_enabled: bool = True
    tracing_mode: TracingMode = TracingMode.DEV
    tracing_service_name: str = "constrain"
    jaeger_endpoint: str = "http://localhost:4317"
    jaeger_insecure: bool = True
    sampling_rate: float = 1.0

    graceful_shutdown_timeout: int = 30

    @classmethod
    def from_yaml(cls, path: str | Path) -> "HarnessConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def apply_env_overrides(self) -> None:
        """Override config values from environment variables."""
        import os

        mapping = {
            "CONSTRAIN_RABBITMQ_URL": "rabbitmq_url",
            "CONSTRAIN_REDIS_URL": "redis_url",
            "CONSTRAIN_POSTGRES_DSN": "postgres_dsn",
            "CONSTRAIN_MODE": "mode",
            "CONSTRAIN_L2_THRESHOLD": "l2_confidence_threshold",
            "CONSTRAIN_TRACING_MODE": "tracing_mode",
            "CONSTRAIN_SERVICE_NAME": "tracing_service_name",
            "CONSTRAIN_JAEGER_ENDPOINT": "jaeger_endpoint",
            "CONSTRAIN_SAMPLING_RATE": "sampling_rate",
            "CONSTRAIN_BUS_BACKEND": "bus_backend",
            "CONSTRAIN_STATE_STORE_BACKEND": "state_store_backend",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "jaeger_endpoint",
        }
        for env_key, config_key in mapping.items():
            value = os.environ.get(env_key)
            if value is not None:
                field = self.model_fields[config_key]
                if field.annotation is float:
                    setattr(self, config_key, float(value))
                elif field.annotation is int:
                    setattr(self, config_key, int(value))
                elif field.annotation is bool:
                    setattr(self, config_key, value.lower() in ("true", "1", "yes"))
                else:
                    setattr(self, config_key, value)
