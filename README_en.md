# Constrain

<p align="center">
  <img src="./docs/images/logo-wide.png" alt="Constrain Logo" width="100%"/>
</p>

**Constrain to Unleash.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](./LICENSE)

---

## Why "Constrain"?

Because we believe: **true autonomy is born from clear boundaries.**

Constrain doesn't grant AI Agents infinite freedom — it grants them maximum autonomy within deterministic boundaries. Powered by three core engines — **Commander**, **Arbiter**, and **StateMachine** — combined with pseudo-idempotency, layered quality gates, and full-stack observability, Constrain elevates AI Agents from "it works" to "it works at production scale."

---

## Architecture

```text
┌─────────────────────────────────────────────────┐
│                   Harness                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │Commander │  │ Arbiter  │  │ StateMachine │  │
│  │  DAG     │  │ Conflict │  │  State       │  │
│  │  Scheduler│  │ Resolver │  │  Manager     │  │
│  └─────┬────┘  └────┬─────┘  └──────┬───────┘  │
│        │            │               │           │
│  ┌─────┴────────────┴───────────────┴────────┐  │
│  │              EventBus                      │  │
│  └─────┬──────────────────────────────┬──────┘  │
│        │                              │         │
│  ┌─────┴─────┐                ┌───────┴─────┐  │
│  │  Agent α  │      ...      │  Agent ω    │  │
│  │ ┌───────┐ │                │ ┌─────────┐ │  │
│  │ │Skills │ │                │ │ Skills  │ │  │
│  │ └───────┘ │                │ └─────────┘ │  │
│  └───────────┘                └─────────────┘  │
│        │                              │         │
│  ┌─────┴──────────────────────────────┴──────┐  │
│  │   Gate  │  Tracing  │  Skill Registry    │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Three Core Engines

| Engine | Codename | Responsibility |
|--------|----------|---------------|
| Commander | **Commander** | Parses workflow DAGs, decomposes tasks, publishes to EventBus — never executes logic |
| Arbiter | **Arbiter** | Distributed resource locks, conflict resolution, retry decisions, hot-reloaded policies |
| StateMachine | **StateMachine** | Strictly bounded state transitions, event-sourced persistence, supports pause/resume/interactive wait |

### Key Design Decisions

- **Pseudo-Idempotency**: Parameter lock-in + input hash caching enables safe retries of AI-generated tasks.
- **Layered Quality Gates (Gate)** : L1 hard compliance → L2 flexible technical validation → L3 human creative arbitration.
- **Full-Stack Observability (Tracing)** : Built on OpenTelemetry + Jaeger — a single Trace ID follows every path from user action to AI inference.
- **Progressive Deployment**: Runs in-memory out of the box on a single machine; swap in RabbitMQ + Redis + PostgreSQL for production.

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup

```bash
# Clone the repo
cd constrain

# Create virtual environment and install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run the hello-world example
uv run python examples/hello-world/main.py
```

### Hello World

```python
import asyncio
from core.harness import Harness, HarnessConfig
from skill import BaseSkill, idempotent

class GreetingSkill(BaseSkill):
    name = "greeting"
    version = "1.0.0"

    @idempotent(ttl=3600)
    async def execute(self, input_data, parameters, trace_id):
        name = input_data.get("name", "World")
        return {"greeting": f"Hello, {name}!"}

async def main():
    forge = Harness(HarnessConfig(mode="memory"))  # Single-node, zero dependencies
    forge.register_skill(GreetingSkill())
    await forge.start()
    run_id = await forge.execute_workflow("hello_world", {"name": "Constrain"})
    await forge.shutdown()

asyncio.run(main())
```

More examples in the `examples/hello-world/` directory.

---

## CLI Tool

Constrain ships with a built-in CLI for scaffolding and project management.

```bash
# See available commands
uv run constrain --help

# Scaffold a new project
uv run constrain init my-project

# Generate components from templates
cd my-project
uv run constrain new skill my-task
uv run constrain new agent worker
uv run constrain new workflow data-pipeline

# List project components
uv run constrain list skills
uv run constrain list agents
uv run constrain list workflows
```

### Commands

| Command | Description |
|---------|-------------|
| `init [name]` | Scaffold a new Constrain project with `constrain.yaml`, `skills/`, `agents/`, `workflows/`, and a `run.py` entry point |
| `new skill <name>` | Generate a new skill class from template |
| `new agent <name>` | Generate a new agent class from template |
| `new workflow <name>` | Generate a new workflow YAML definition |
| `list skills\|agents\|workflows` | List existing project components |
| `run [workflow]` | Execute a workflow (`--dev` for in-memory mode, `-i key=val` for inputs) |

---

## Docker Deployment

### Full Production Stack

```bash
# Start all services with one command (Jaeger + Redis + RabbitMQ + PostgreSQL + App)
docker compose up -d

# Tail logs
docker compose logs -f app

# Stop and clean up
docker compose down -v
```

After startup, visit:
- **Jaeger UI**: http://localhost:16686
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)

### Standalone Build

```bash
# Build the image
docker build -t constrain:latest .

# Run a custom agent
docker run --rm -v ./my_agent.py:/app/agent.py constrain python agent.py
```

### Production Configuration

Configure via environment variables (full reference in `config/production.yaml`):

| Variable | Description | Default |
|----------|-------------|---------|
| `CONSTRAIN_MODE` | Runtime mode | `memory` |
| `CONSTRAIN_BUS_BACKEND` | Event bus backend (`rabbitmq`/`memory`) | `memory` |
| `CONSTRAIN_RABBITMQ_URL` | RabbitMQ connection string | `amqp://guest:guest@localhost:5672/` |
| `CONSTRAIN_STATE_STORE_BACKEND` | State store backend (`postgres`/`sqlite`/`memory`) | `memory` |
| `CONSTRAIN_POSTGRES_DSN` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/constrain` |
| `CONSTRAIN_REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `CONSTRAIN_TRACING_MODE` | Tracing mode (`production`/`dev`) | `dev` |
| `CONSTRAIN_JAEGER_ENDPOINT` | Jaeger OTLP gRPC endpoint | `http://localhost:4317` |
| `CONSTRAIN_SAMPLING_RATE` | Sampling rate [0,1] | `1.0` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTel export endpoint (takes precedence) | Same as CONSTRAIN_JAEGER_ENDPOINT |

```bash
# Single-container production mode
docker run --rm \
  -e CONSTRAIN_MODE=production \
  -e CONSTRAIN_BUS_BACKEND=rabbitmq \
  -e CONSTRAIN_RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/ \
  -e CONSTRAIN_TRACING_MODE=production \
  --network constrain_default \
  constrain:latest python app.py
```

---

## Comparison with Similar Frameworks

| Feature | Constrain | LangGraph | CrewAI | AutoGen | Temporal |
|---------|-----------|-----------|--------|---------|----------|
| DAG Workflow Orchestration | ✅ | ✅ | Partial | ❌ | ✅ |
| Distributed Locks / Conflict Resolution | ✅ **Arbiter** | ❌ | ❌ | ❌ | ❌ |
| Event-Sourced State Machine | ✅ **StateMachine** | ✅ | ❌ | ❌ | ✅ |
| AI Pseudo-Idempotency | ✅ **Built-in** | ❌ | ❌ | ❌ | ❌ |
| Layered Quality Gates | ✅ **Gate** | ❌ | ❌ | ❌ | ❌ |
| Full Trace (OTel + Jaeger) | ✅ **Tracing** | Partial | ❌ | ❌ | Partial |
| Zero-Dependency Single-Node Mode | ✅ | ❌ | ❌ | ❌ | ❌ |

**Constrain's unique position**: Not an experimental Agent framework, but an **AI-native, production-ready Agentic orchestration platform** — bridging the engineering gap between demo and industrial deployment.

---

## Directory Structure

```text
.
├── cli/                     # CLI scaffolding tool
│   ├── main.py              # Entry point (click)
│   ├── templates.py         # Scaffold templates
│   └── commands/            # CLI subcommands (init, new, list, run)
├── core/                    # Core engines
│   ├── commander/           # Commander: DAG orchestration engine
│   ├── arbiter/             # Arbiter: resource locks + retry + policies
│   ├── state_machine/       # StateMachine: event sourcing + lifecycle
│   ├── event_bus/           # Event bus (Memory / RabbitMQ / Redis)
│   │   └── backends/
│   ├── gate/                # Layered quality gates (L1/L2/L3)
│   ├── tracing/             # Full-stack observability (OpenTelemetry + Jaeger)
│   └── harness/             # Execution container + config + middleware
├── agent/                   # Agent base class + registry
├── skill/                   # Skill base class + @idempotent decorator
├── adapters/                # Redis / PostgreSQL / RabbitMQ adapters
├── config/                  # Production configuration
│   └── production.yaml
├── examples/                # Example projects
│   └── hello-world/
├── tests/                   # Unit tests (37 passing)
├── Dockerfile               # Multi-stage build (uv + alpine)
├── docker-compose.yml       # Full-stack orchestration (6 services)
├── pyproject.toml           # Dependency management (uv + hatchling)
├── uv.lock                  # Lock file
└── .env.example             # Environment variable template
```

---

## Contributing

Issues and PRs are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

Apache 2.0 © 2025 Constrain Contributors
