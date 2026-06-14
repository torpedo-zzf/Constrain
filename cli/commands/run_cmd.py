"""constrain run — execute a workflow."""

import asyncio
import json
import sys
from pathlib import Path

import click
import yaml


@click.command()
@click.argument("workflow_name", required=False)
@click.option("-i", "--input", "input_data", multiple=True, help="Input key=value pairs")
@click.option("-f", "--file", "input_file", default=None, help="JSON/YAML input file")
@click.option("--dev", is_flag=True, default=False, help="Use memory backend")
def run(workflow_name: str | None, input_data: tuple[str], input_file: str | None, dev: bool) -> None:
    """Run a workflow.

    If WORKFLOW_NAME is omitted, runs in "listener mode" — the Harness
    subscribes to the event bus and waits for workflow triggers.
    """
    if workflow_name is None:
        _run_listener()
        return

    # Resolve input
    inputs: dict = {}
    if input_file:
        path = Path(input_file)
        raw = path.read_text()
        inputs = yaml.safe_load(raw) if path.suffix in (".yaml", ".yml") else json.loads(raw)
    for kv in input_data:
        k, _, v = kv.partition("=")
        inputs[k] = v

    _execute_workflow(workflow_name, inputs, dev)


def _execute_workflow(name: str, inputs: dict, dev: bool) -> None:
    """Import and run a workflow via the Harness."""
    sys.path.insert(0, str(Path.cwd()))

    try:
        from core.harness import Harness, HarnessConfig
    except ImportError:
        click.secho(
            "Error: cannot import Constrain. Make sure you're in a project directory "
            "with Constrain installed (uv sync).",
            fg="red",
        )
        sys.exit(1)

    async def _run():
        config = HarnessConfig(
            mode="memory" if dev else "production",
            bus_backend="memory" if dev else None,
            state_store_backend="memory" if dev else None,
            skill_paths=["skills"],
            workflow_paths=["workflows"],
        )
        harness = Harness(config)
        await harness.start()

        click.echo(f"Running workflow '{name}' with input: {inputs}")
        run_id = await harness.execute_workflow(name, inputs)
        click.echo(f"Workflow submitted — run_id: {run_id}")
        await harness.shutdown()

    asyncio.run(_run())


def _run_listener() -> None:
    """Start a long-running Harness that listens for incoming workflow triggers."""
    sys.path.insert(0, str(Path.cwd()))

    try:
        from core.harness import Harness, HarnessConfig
    except ImportError:
        click.secho(
            "Error: cannot import Constrain. Make sure you're in a project directory "
            "with Constrain installed (uv sync).",
            fg="red",
        )
        sys.exit(1)

    async def _listen():
        config = HarnessConfig(
            mode="memory",
            skill_paths=["skills"],
            workflow_paths=["workflows"],
        )
        harness = Harness(config)
        await harness.start()
        click.echo("Constrain Harness is running. Press Ctrl+C to stop.")
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            click.echo("\nShutting down...")
        finally:
            await harness.shutdown()

    asyncio.run(_listen())
