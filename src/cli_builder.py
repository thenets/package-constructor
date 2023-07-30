import click
import helpers
import os
import json
import yaml
import requests


_global = helpers.get_global()
logger = helpers.get_logger()


@click.command()
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
def cmd_build(clone_path):
    """Build a container image using Cachito servers"""
    print("hello")

# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_server = click.Group("builder", help="Container builder commands")
    cmd_server.add_command(name="build", cmd=cmd_build)
    cli.add_command(cmd_server)

