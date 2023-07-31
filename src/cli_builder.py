import click
import helpers
import os


_global = helpers.get_global()
logger = helpers.get_logger()


@click.command()
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
# option: --file, -f
@click.option(
    "--file",
    "-f",
    default="./Containerfile",
    help="Path to the Containerfile to build",
)
# option: --build-context
@click.option(
    "--build-context",
    "-c",
    help="Path to the build context. Defaults to the directory of the Containerfile",
)
def cmd_build(clone_path, file, build_context):
    """Build a container image using Cachito servers"""

    # Check if Containerfile exists
    if not os.path.isfile(file):
        logger.error("Containerfile not found: " + file)
        exit(1)

    services = helpers.get_services(clone_path)

    file_abs = os.path.abspath(file)
    if build_context:
        build_context_abs = os.path.abspath(build_context)
    else:
        build_context_abs = os.path.dirname(file_abs)

    # TODO add interceptor
    # TODO add env file creation
    # TODO add limited DNS resolution

    cmd_out = helpers.run(["podman", "build", "-f", file_abs, "-t", "test", build_context_abs])
    if cmd_out.returncode != 0:
        logger.error("Error building container image")
        exit(1)
    print(cmd_out.stdout.decode("utf-8"))






# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_server = click.Group("builder", help="Container builder commands")
    cmd_server.add_command(name="build", cmd=cmd_build)
    cli.add_command(cmd_server)
