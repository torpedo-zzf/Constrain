# ============================================================
# Multi-stage Docker image for Constrain framework
#
# Build:
#   docker build -t constrain:latest .
#
# Run with custom app:
#   docker run --rm -v ./app.py:/app/app.py constrain python app.py
#
# Run with docker-compose:
#   docker compose up
# ============================================================

# ---- Build stage ----
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

WORKDIR /app

# Install system build deps (needed for some native extensions)
RUN apk add --no-cache gcc musl-dev

# Copy dependency metadata first for Docker layer caching
COPY pyproject.toml uv.lock ./

# Install all optional extras into the venv
RUN uv sync \
    --frozen \
    --no-dev \
    --extra rabbitmq \
    --extra redis \
    --extra postgres \
    --extra jaeger

# Copy the source packages
COPY core/ core/
COPY agent/ agent/
COPY skill/ skill/
COPY adapters/ adapters/

# Install the project itself (uses cached deps)
RUN uv sync \
    --frozen \
    --no-dev \
    --extra rabbitmq \
    --extra redis \
    --extra postgres \
    --extra jaeger

# ---- Runtime stage ----
FROM python:3.12-alpine

WORKDIR /app

# Runtime system deps
RUN apk add --no-cache ca-certificates

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source packages (for editable install awareness at runtime)
COPY --from=builder /app/core /app/core
COPY --from=builder /app/agent /app/agent
COPY --from=builder /app/skill /app/skill
COPY --from=builder /app/adapters /app/adapters

ENV \
    # Prefer the venv binaries
    PATH="/app/.venv/bin:$PATH" \
    # Python settings
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Default tracing endpoint (can override at runtime)
    OTEL_EXPORTER_OTLP_ENDPOINT="http://jaeger:4317" \
    CONSTRAIN_TRACING_MODE="production"

# Verify the framework is importable
RUN python -c "from core.harness import Harness; print('Constrain framework ready')"

ENTRYPOINT ["python"]
CMD ["-c", "print('Constrain framework 0.1.0 — use docker compose up for full stack')"]
