"""constrain list — inspect project components."""

from pathlib import Path

import click
import yaml


@click.group()
def list_cmd() -> None:
    """List project components."""


@list_cmd.command()
def skills() -> None:
    """List available skills."""
    skill_dirs = _find_dirs(["skills"])
    if not skill_dirs:
        click.echo("No skills directory found.")
        return

    for skill_dir in skill_dirs:
        for f in sorted(skill_dir.glob("*.py")):
            if f.name == "__init__.py":
                continue
            click.echo(f"  {f.parent.name}/{f.stem}")


@list_cmd.command()
def agents() -> None:
    """List available agents."""
    agent_dirs = _find_dirs(["agents"])
    if not agent_dirs:
        click.echo("No agents directory found.")
        return

    for agent_dir in agent_dirs:
        for f in sorted(agent_dir.glob("*.py")):
            if f.name == "__init__.py":
                continue
            click.echo(f"  {f.parent.name}/{f.stem}")


@list_cmd.command()
def workflows() -> None:
    """List available workflow definitions."""
    wf_dirs = _find_dirs(["workflows"])

    if not wf_dirs:
        # Try to load from the framework's registered workflows
        click.echo("No workflows directory found.")
        return

    for wf_dir in wf_dirs:
        for f in sorted(wf_dir.glob("*.yaml")):
            try:
                doc = yaml.safe_load(f.read_text())
                name = doc.get("name", f.stem) if doc else f.stem
                desc = doc.get("description", "") if doc else ""
                desc_str = f"  — {desc}" if desc else ""
                click.echo(f"  {name}{desc_str}")
            except Exception:
                click.echo(f"  {f.stem}  (parse error)")


def _find_dirs(candidates: list[str]) -> list[Path]:
    cwd = Path.cwd()
    return [d for d in (cwd / p for p in candidates) if d.is_dir()]
