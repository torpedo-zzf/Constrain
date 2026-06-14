"""constrain new — generate skills, agents, and workflows."""

from pathlib import Path
import re

import click

from ..templates import (
    AGENT_TEMPLATE,
    SKILL_TEMPLATE,
    WORKFLOW_TEMPLATE,
)


def _pascal_case(name: str) -> str:
    return "".join(word.capitalize() for word in re.split(r"[-_\s]+", name))


def _snake_case(name: str) -> str:
    return re.sub(r"[- ]+", "_", name).lower()


def _kebab_case(name: str) -> str:
    return re.sub(r"[_ ]+", "-", name).lower()


@click.group()
def new() -> None:
    """Generate new components."""


@new.command()
@click.argument("name")
@click.option("-d", "--dir", default="skills", help="Target directory")
@click.option("--description", default="", help="Skill description")
def skill(name: str, dir: str, description: str) -> None:
    """Generate a new skill."""
    target = Path.cwd() / dir / f"{_snake_case(name)}.py"
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        click.confirm(f"{target} already exists. Overwrite?", abort=True)

    content = SKILL_TEMPLATE.format(
        class_name=_pascal_case(name) + "Skill",
        skill_name=_kebab_case(name),
        description=description or f"{name} skill",
    )
    _ensure_init(target.parent)
    target.write_text(content)
    click.echo(f"  create  {target}")


@new.command()
@click.argument("name")
@click.option("-d", "--dir", default="agents", help="Target directory")
@click.option("--description", default="", help="Agent description")
def agent(name: str, dir: str, description: str) -> None:
    """Generate a new agent."""
    target = Path.cwd() / dir / f"{_snake_case(name)}.py"
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        click.confirm(f"{target} already exists. Overwrite?", abort=True)

    content = AGENT_TEMPLATE.format(
        class_name=_pascal_case(name) + "Agent",
        agent_name=_kebab_case(name),
        description=description or f"{name} agent",
    )
    _ensure_init(target.parent)
    target.write_text(content)
    click.echo(f"  create  {target}")


@new.command()
@click.argument("name")
@click.option("-d", "--dir", default="workflows", help="Target directory")
@click.option("--skill", default="hello", help="Primary skill used in workflow")
@click.option("--description", default="", help="Workflow description")
def workflow(name: str, dir: str, skill: str, description: str) -> None:
    """Generate a new workflow definition."""
    target = Path.cwd() / dir / f"{_kebab_case(name)}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        click.confirm(f"{target} already exists. Overwrite?", abort=True)

    content = WORKFLOW_TEMPLATE.format(
        workflow_name=_kebab_case(name),
        description=description or f"{name} workflow",
        skill_name=_kebab_case(skill),
    )
    target.write_text(content)
    click.echo(f"  create  {target}")


def _ensure_init(pkg_dir: Path) -> None:
    """Create __init__.py if the directory doesn't have one."""
    init_file = pkg_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Auto-generated\n")
        click.echo(f"  create  {init_file}")
