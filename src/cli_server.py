import os
import time

import click
import pytest
import yaml

import common

_global = common.get_global()
logger = common.get_logger()

_cachito_repo_path = common.get_cachito_repository_path()


def _check_dependencies():
    # Check podman
    if not common.check_executable("podman"):
        logger.error("podman is not available in the PATH")
        exit(1)
    # Check podman-compose
    if not common.check_executable("podman-compose"):
        logger.error("podman-compose is not available in the PATH")
        exit(1)
    # Check git
    if not common.check_executable("git"):
        logger.error("git is not available in the PATH")
        exit(1)


def _get_compose_file_data(cachito_repo_path: str):
    compose_file = None
    # Search for files, in order of preference
    for file in ["container-compose.yml", "podman-compose.yaml", "docker-compose.yml"]:
        if os.path.isfile(os.path.join(cachito_repo_path, file)):
            compose_file = file
            break
    with open(os.path.join(cachito_repo_path, compose_file), "r") as f:
        compose_data = yaml.safe_load(f)
    return compose_data


# Shared functions
# ====================
def start(cachito_repo_path: str):
    """Start the Cachito server if is not running

    Returns:
        dict: services data
    """
    # Basic checks
    _check_dependencies()
    if not common.cachito_repo_exists(cachito_repo_path):
        # Clone cachito
        logger.info("Cloning Cachito repository")
        common.run(["git", "clone", _global["cachito_git_url"], cachito_repo_path])

    logger.info("Fixing volume permissions")
    compose = _get_compose_file_data(cachito_repo_path)

    # Fix nexus permissions
    nexus_uid = common.run(
        [
            "podman",
            "run",
            "-it",
            "--rm",
            "--entrypoint=",
            compose["services"]["nexus"]["image"],
            "id",
            "-u",
        ]
    ).stdout.strip()
    nexus_gid = common.run(
        [
            "podman",
            "run",
            "-it",
            "--rm",
            "--entrypoint=",
            compose["services"]["nexus"]["image"],
            "id",
            "-g",
        ]
    ).stdout.strip()
    logger.info("Setting up docker-compose.yml")
    volume_path = os.path.join(
        cachito_repo_path, compose["services"]["nexus"]["volumes"][0].split(":")[0]
    )
    os.makedirs(volume_path, exist_ok=True)
    common.run(
        ["podman", "unshare", "chown", "-R", f"{nexus_uid}:{nexus_gid}", volume_path]
    )

    # Start the services
    common.run(["podman-compose", "up", "-d"], cwd=cachito_repo_path)
    logger.info("Waiting for services to be operational. Sleeping for 30 seconds")
    time.sleep(30)

    # Get services data
    services = common.get_services(cachito_repo_path)
    logger.info("Services are operational")
    return services


def stop(cachito_repo_path: str):
    # Basic checks
    _check_dependencies()
    if not common.cachito_repo_exists(cachito_repo_path):
        logger.error("Cachito repository does not exist")
        exit(1)

    logger.info("Stopping Cachito server")
    common.run(
        ["podman-compose", "down", "-v", "--remove-orphans"], cwd=cachito_repo_path
    )
    logger.info("Removing volumes")
    compose = _get_compose_file_data(cachito_repo_path)
    volume_path = os.path.join(
        cachito_repo_path, compose["services"]["nexus"]["volumes"][0].split(":")[0]
    )
    common.run(["podman", "unshare", "rm", "-rf", volume_path])


def restart(cachito_repo_path: str):
    """Restart the Cachito server if is running or start it if is not running"""
    if common.is_running(cachito_repo_path):
        logger.info("Restarting Cachito server")
        stop(cachito_repo_path)
        start(cachito_repo_path)
    else:
        logger.info("Starting Cachito server")
        start(cachito_repo_path)


# Click commands
# ====================
def _print_status(cachito_repo_path, services=None):
    logger.info("Retrieving Cachito server containers list")
    if services is None:
        services = common.get_services(cachito_repo_path)
    click.echo("All services are operational")
    click.echo(f"  Athens  : {services['athens']['url_local']}")
    click.echo(f"  Nexus   : {services['nexus']['url_local']}")
    click.echo(f"  Cachito : {services['cachito']['url_local']}")
    click.echo("")


@click.command()
def cmd_start():
    """start a new Cachito server with all the related services."""
    if common.is_running(_cachito_repo_path):
        click.echo("Cachito server is already running")
        services = common.get_services(_cachito_repo_path)
        _print_status(_cachito_repo_path, services)
        exit(0)
    services = start(_cachito_repo_path)
    _print_status(_cachito_repo_path, services)


@click.command()
def cmd_stop():
    """Stop the Cachito server"""
    stop(_cachito_repo_path)
    click.echo("Cachito server stopped")


@click.command()
def cmd_status():
    """Show the status of the Cachito server"""
    # Basic checks
    _check_dependencies()
    if not common.cachito_repo_exists(_cachito_repo_path):
        logger.error("Cachito repository does not exist")
        exit(1)

    try:
        _print_status(_cachito_repo_path)
    except:
        logger.error("Cachito server may not be running")
        logger.error("Try starting it with 'cachito server start'")
        exit(1)


@click.command()
def cmd_restart():
    """Restart the Cachito server"""
    restart(_cachito_repo_path)
    _print_status(_cachito_repo_path)


# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_server = click.Group("server", help="Proxy and tool servers")
    cmd_server.add_command(name="start", cmd=cmd_start)
    cmd_server.add_command(name="stop", cmd=cmd_stop)
    cmd_server.add_command(name="status", cmd=cmd_status)
    cmd_server.add_command(name="restart", cmd=cmd_restart)
    cli.add_command(cmd_server)


@pytest.mark.usefixtures("server")
class TestServer:
    def test_status(self, runner):
        # change cwd to something else
        os.chdir("/tmp")
        result = runner.invoke(cmd_status, [])
        assert result.exit_code == 0
        assert "All services are operational" in result.output

    def test_status_when_not_running(self, runner):
        result = runner.invoke(cmd_status, [])
        assert result.exit_code == 0
        assert "All services are operational" not in result.output

    def test_start_twice(self, runner):
        result = runner.invoke(cmd_start, [])
        assert result.exit_code == 0
        assert "Cachito server is already running" in result.output
        assert "All services are operational" in result.output
