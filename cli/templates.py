"""Template strings for scaffolding."""

PROJECT_CONSTRAIN_YAML = """\
# Constrain project configuration
project_name: "{name}"
version: "0.1.0"

# Execution mode: memory | production
mode: memory

# Event bus backend: memory | rabbitmq | redis
bus_backend: memory

# State store backend: memory | postgres | sqlite
state_store_backend: memory

# Tracing mode: dev | production
tracing_mode: dev

# Skill paths to auto-discover
skill_paths:
  - skills

# Workflow paths to auto-discover
workflow_paths:
  - workflows
"""

SKILL_INIT = """\
# Auto-generated skills package
"""

SKILL_TEMPLATE = """\
from constrain_framework.skill import BaseSkill, idempotent


class {class_name}(BaseSkill):
    name = "{skill_name}"
    version = "1.0.0"
    description = "{description}"

    @idempotent(ttl=3600)
    async def execute(
        self,
        input_data: dict,
        parameters: dict,
        trace_id: str,
    ) -> dict:
        \"\"\"Execute the skill logic.\"\"\"
        # TODO: implement your skill logic here
        return {{"result": f"Hello from {{self.name}}!"}}
"""

AGENT_INIT = """\
# Auto-generated agents package
"""

AGENT_TEMPLATE = """\
from constrain_framework.agent import BaseAgent
from constrain_framework.core.event_bus import EventBus


class {class_name}(BaseAgent):
    name = "{agent_name}"
    description = "{description}"

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)

    async def execute(
        self,
        skill_name: str,
        input_data: dict,
        trace_id: str,
    ) -> dict:
        \"\"\"Execute the requested skill.\"\"\"
        # TODO: implement skill dispatch logic
        # skill = skill_registry.get(skill_name)
        # return await skill.execute(input_data, {{}}, trace_id)
        return {{"status": "ack", "skill": skill_name}}
"""

WORKFLOW_TEMPLATE = """\
name: {workflow_name}
version: "1.0.0"
description: "{description}"

tasks:
  - id: task_1
    skill: "{skill_name}"
    input:
      message: "Hello from task 1"
    next: task_2

  - id: task_2
    skill: "{skill_name}"
    input:
      message: "Hello from task 2"
"""

ENV_EXAMPLE = """\
# Constrain environment variables

## Runtime mode: memory | production
CONSTRAIN_MODE=memory

## Event bus backend: memory | rabbitmq | redis
CONSTRAIN_BUS_BACKEND=memory

## State store backend: memory | postgres | sqlite
CONSTRAIN_STATE_STORE_BACKEND=memory

## Tracing mode: dev | production
CONSTRAIN_TRACING_MODE=dev

## RabbitMQ (optional)
# CONSTRAIN_RABBITMQ_URL=amqp://guest:guest@localhost:5672/

## PostgreSQL (optional)
# CONSTRAIN_POSTGRES_DSN=postgresql://user:pass@localhost:5432/constrain

## Redis (optional)
# CONSTRAIN_REDIS_URL=redis://localhost:6379/0

## Jaeger / OpenTelemetry (optional)
# CONSTRAIN_JAEGER_ENDPOINT=http://localhost:4317
# CONSTRAIN_SAMPLING_RATE=1.0
"""

RUNNER_SCRIPT = """\
#!/usr/bin/env python
\"\"\"Auto-generated runner script for the {name} project.\"\"\"

import asyncio
from core.harness import Harness, HarnessConfig


async def main():
    config = HarnessConfig(
        mode="memory",
        bus_backend="memory",
        state_store_backend="memory",
        skill_paths=["skills"],
        workflow_paths=["workflows"],
    )
    harness = Harness(config)

    @harness.on("workflow.completed")
    async def on_completed(event):
        print(f"[completed] workflow={{event.headers.event_id}}")

    @harness.on("workflow.failed")
    async def on_failed(event):
        print(f"[failed] workflow={{event.headers.event_id}}: {{event.payload}}")

    await harness.start()
    print("Constrain Harness is running. Press Ctrl+C to stop.")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await harness.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
"""

__all__ = [
    "PROJECT_CONSTRAIN_YAML",
    "SKILL_INIT",
    "SKILL_TEMPLATE",
    "AGENT_INIT",
    "AGENT_TEMPLATE",
    "WORKFLOW_TEMPLATE",
    "ENV_EXAMPLE",
    "RUNNER_SCRIPT",
]
