#!/usr/bin/env python3
"""Hello World example for the Constrain framework.

Demonstrates:
- In-memory mode (zero external dependencies)
- Custom Skill definition with idempotency
- Single-skill workflow execution via the Harness API
"""

import asyncio
import logging

from core.harness import Harness, HarnessConfig
from skill import BaseSkill, idempotent

logging.basicConfig(level=logging.INFO)


# --- Skills ---

class GreetingSkill(BaseSkill):
    name = "greeting"
    version = "1.0.0"
    description = "Generates a greeting message"

    @idempotent(ttl=3600)
    async def execute(self, input_data, parameters, trace_id):
        name = input_data.get("name", "World")
        return {"greeting": f"Hello, {name}!"}


class UppercaseSkill(BaseSkill):
    name = "uppercase"
    version = "1.0.0"
    description = "Converts text to uppercase"

    async def execute(self, input_data, parameters, trace_id):
        text = input_data.get("text", "")
        return {"result": text.upper()}


# --- Workflow Definitions ---

def build_greeting_workflow():
    from core.commander.models import TaskDef, WorkflowDef

    return WorkflowDef(
        name="hello_world",
        version="1.0.0",
        tasks=[
            TaskDef(
                task_id="step1",
                skill_name="greeting",
                input_mapping={"name": "$input.name"},
            ),
        ],
        edges=[],
    )


def build_uppercase_workflow():
    from core.commander.models import TaskDef, WorkflowDef

    return WorkflowDef(
        name="uppercase",
        version="1.0.0",
        tasks=[
            TaskDef(
                task_id="step1",
                skill_name="uppercase",
                input_mapping={"text": "$input.text"},
            ),
        ],
        edges=[],
    )


# --- Simple Agent ---

class SimpleAgent:
    """Minimal agent that dispatches task events to the correct skill."""

    def __init__(self, harness: Harness) -> None:
        self._harness = harness

    async def handle_task(self, event) -> None:
        from core.event_bus import Event

        payload = event.payload
        skill_name = payload.get("skill_name", "")
        task_input = payload.get("input", {})

        skill = self._harness._skill_registry.get(skill_name)
        if skill is None:
            raise ValueError(f"Unknown skill: {skill_name}")

        trace_id = event.trace_id or ""
        result = await skill.execute(task_input, {}, trace_id)

        await self._harness._event_bus.publish(
            Event.create(
                "TaskCompleted",
                {
                    "run_id": payload.get("run_id"),
                    "task_id": payload.get("task_id"),
                    "result": result,
                },
                trace_id=trace_id,
            ),
            "task.completed",
        )


async def main():
    config = HarnessConfig(mode="memory", tracing_enabled=True)
    harness = Harness(config)

    # Register skills
    harness.register_skill(GreetingSkill())
    harness.register_skill(UppercaseSkill())

    # Register workflows
    harness._skill_registry.register_workflow("hello_world", build_greeting_workflow())
    harness._skill_registry.register_workflow("uppercase", build_uppercase_workflow())

    # Start the harness
    await harness.start()

    # Wire up a simple agent to handle task dispatch events
    agent = SimpleAgent(harness)
    await harness._event_bus.subscribe("TaskDispatched", agent.handle_task, "example-agent")

    # --- Execute greeting workflow ---
    run_id = await harness.execute_workflow("hello_world", {"name": "Constrain"})
    print(f"\n--- Workflow: hello_world ---")
    print(f"Submitted | run_id={run_id}")

    await asyncio.sleep(0.5)

    status = await harness.get_status(run_id)
    print(f"Status: {status.status if status else 'unknown'}")
    if status:
        for tid, ts in status.task_statuses.items():
            print(f"  Task {tid}: {ts.value}")

    # --- Execute uppercase workflow ---
    run_id2 = await harness.execute_workflow("uppercase", {"text": "hello from constrain"})
    print(f"\n--- Workflow: uppercase ---")
    print(f"Submitted | run_id={run_id2}")

    await asyncio.sleep(0.5)

    status2 = await harness.get_status(run_id2)
    print(f"Status: {status2.status if status2 else 'unknown'}")
    if status2:
        for tid, ts in status2.task_statuses.items():
            print(f"  Task {tid}: {ts.value}")

    await harness.shutdown()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
