"""constrain init — scaffold a new Constrain project."""

import os
from pathlib import Path

import click

from ..templates import (
    AGENT_INIT,
    AGENT_TEMPLATE,
    ENV_EXAMPLE,
    PROJECT_CONSTRAIN_YAML,
    RUNNER_SCRIPT,
    SKILL_INIT,
    SKILL_TEMPLATE,
    WORKFLOW_TEMPLATE,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"))
    click.echo(f"  create  {path}")


@click.command()
@click.argument("name", default="my-constrain-project")
@click.option(
    "-d", "--dir",
    default=None,
    help="Target directory (default: <name> in current dir)",
)
def init(name: str, dir: str | None) -> None:
    """Scaffold a new Constrain project."""
    target = Path(dir).resolve() if dir else Path.cwd() / name

    if target.exists() and any(target.iterdir()):
        click.confirm(
            f"Directory {target} is not empty. Continue?",
            abort=True,
        )

    click.echo(f"Initializing Constrain project '{name}' in {target} ...\n")

    # constrain.yaml
    _write(
        target / "constrain.yaml",
        PROJECT_CONSTRAIN_YAML.format(name=name),
    )

    # Skills
    _write(target / "skills" / "__init__.py", SKILL_INIT)
    _write(
        target / "skills" / "hello.py",
        SKILL_TEMPLATE.format(
            class_name="HelloSkill",
            skill_name="hello",
            description="A hello world skill",
        ),
    )

    # Agents
    _write(target / "agents" / "__init__.py", AGENT_INIT)
    _write(
        target / "agents" / "worker.py",
        AGENT_TEMPLATE.format(
            class_name="WorkerAgent",
            agent_name="worker",
            description="Default worker agent",
        ),
    )

    # Workflows
    _write(
        target / "workflows" / "hello_world.yaml",
        WORKFLOW_TEMPLATE.format(
            workflow_name="hello_world",
            description="A simple hello world workflow",
            skill_name="hello",
        ),
    )

    # Runner
    _write(target / "run.py", RUNNER_SCRIPT.format(name=name))

    # Env example
    _write(target / ".env.example", ENV_EXAMPLE)

    # Make run.py executable
    os.chmod(target / "run.py", 0o755)

    click.echo()
    click.secho("Done! Next steps:", bold=True)
    click.echo(f"  cd {target}")
    click.echo("  uv sync")
    click.echo("  uv run python run.py")
    click.echo()
    click.echo("Or generate more components:")
    click.echo("  constrain new skill <name>")
    click.echo("  constrain new agent <name>")
    click.echo("  constrain new workflow <name>")
