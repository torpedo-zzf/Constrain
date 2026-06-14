"""Constrain CLI — Scaffolding & management tool."""

import click

from .commands.init_cmd import init
from .commands.new_cmd import new
from .commands.list_cmd import list_cmd
from .commands.run_cmd import run


@click.group()
@click.version_option(version="0.1.0", prog_name="constrain")
def cli() -> None:
    """Constrain — production-grade multi-agent orchestration framework."""


cli.add_command(init)
cli.add_command(new)
cli.add_command(list_cmd, name="list")
cli.add_command(run)

if __name__ == "__main__":
    cli()
