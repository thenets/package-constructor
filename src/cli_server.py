import click
import helpers
import os
import json
import yaml
import requests


_global = helpers.get_global()
logger = helpers.get_logger()


def _check_dependencies():
    # Check podman
    if not helpers.check_executable("podman"):
        logger.error("podman is not available in the PATH")
        exit(1)
    # Check podman-compose
    if not helpers.check_executable("podman-compose"):
        logger.error("podman-compose is not available in the PATH")
        exit(1)
    # Check git
    if not helpers.check_executable("git"):
        logger.error("git is not available in the PATH")
        exit(1)


def _cachito_repo_exists(repo_path: str):
    """Check if the Cachito repository already exists

    Returns:
        bool: True if the Cachito repository already exists
              False if the Cachito repository does not exist but the path is valid
    """
    if not os.path.isdir(os.path.dirname(repo_path)):
        logger.error("Parent directory does not exist: " + os.path.dirname(repo_path))
        exit(1)
    if os.path.isdir(repo_path):
        if os.path.join(repo_path, ".git"):
            logger.info("Git repository identified. Skipping clone")
        else:
            logger.error("Directory already exists and it is not a git repository")
            exit(1)
        return True
    else:
        return False


def _get_compose_file_data(repo_path: str):
    compose_file = None
    # Search for files, in order of preference
    for file in ["container-compose.yml", "podman-compose.yaml", "docker-compose.yml"]:
        if os.path.isfile(os.path.join(repo_path, file)):
            compose_file = file
            break
    with open(os.path.join(repo_path, compose_file), "r") as f:
        compose_data = yaml.safe_load(f)
    return compose_data


@click.command()
@click.option(
    "--clone-path", "-p", default="./cache/cachito_repo", help="Path to clone the Cachito repository"
)
def cmd_deploy(clone_path):
    """Deploy a new Cachito server with all the related services."""
    clone_path_abs = os.path.abspath(clone_path)

    # Basic checks
    _check_dependencies()
    if not _cachito_repo_exists(clone_path_abs):
        # Clone cachito
        logger.info("Cloning Cachito repository")
        helpers.run(["git", "clone", _global["cachito_git_url"], clone_path_abs])

    logger.info("Fixing volume permissions")
    compose = _get_compose_file_data(clone_path_abs)

    # Fix nexus permissions
    nexus_uid = (
        helpers.run(
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
        )
        .stdout.decode("utf-8")
        .strip()
    )
    nexus_gid = (
        helpers.run(
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
        )
        .stdout.decode("utf-8")
        .strip()
    )
    logger.info("Setting up docker-compose.yml")
    volume_path = os.path.join(
        clone_path_abs, compose["services"]["nexus"]["volumes"][0].split(":")[0]
    )
    os.makedirs(volume_path, exist_ok=True)
    helpers.run(
        ["podman", "unshare", "chown", "-R", f"{nexus_uid}:{nexus_gid}", volume_path]
    )

    # Start the services
    helpers.run(["podman-compose", "up", "-d"], cwd=clone_path_abs)


@click.command()
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
def cmd_stop(clone_path):
    """Stop the Cachito server"""
    clone_path_abs = os.path.abspath(clone_path)

    # Basic checks
    _check_dependencies()
    if not _cachito_repo_exists(clone_path_abs):
        logger.error("Cachito repository does not exist")
        exit(1)

    logger.info("Stopping Cachito server")
    helpers.run(["podman-compose", "down"], cwd=clone_path_abs)


def get_services(repo_path: str):
    """Get the services from the docker-compose.yml file"""
    services = {
        "athens": {},
        "nexus": {},
        "cachito": {},
    }

    # Get data from podman
    podman_project_name = os.path.basename(repo_path)
    cmd_out = helpers.run(
        [
            "podman",
            "ps",
            "-a",
            "--format",
            "json",
            "--filter",
            f"label=io.podman.compose.project={podman_project_name}",
        ],
        cwd=repo_path,
    )
    containers = json.loads(cmd_out.stdout)
    for container in containers:
        service = {}

        # Athens
        if f"{podman_project_name}_athens_1" in container["Names"]:
            if container["State"] != "running":
                logger.fatal("Athens is not running")
                exit(1)
            service["port"] = {
                "host": container["Ports"][0]["host_port"],
                "container": container["Ports"][0]["container_port"],
            }
            service["url"] = f"http://localhost:{service['port']['host']}"
            r = requests.get(service["url"] + "/healthz")
            if r.status_code != 200:
                logger.fatal(f"Error connecting to Athens: {r.status_code}")
                exit(1)
            services["athens"] = service

        # Nexus
        if f"{podman_project_name}_nexus_1" in container["Names"]:
            if container["State"] != "running":
                logger.fatal("Nexus is not running")
                exit(1)
            service["port"] = {
                "host": container["Ports"][0]["host_port"],
                "container": container["Ports"][0]["container_port"],
            }
            service["url"] = f"http://localhost:{service['port']['host']}"
            r = requests.get(service["url"])
            if r.status_code != 200:
                logger.fatal(f"Error connecting to Nexus: {r.status_code}")
                exit(1)
            services["nexus"] = service
            # Test nexus credentials
            nexus_user = "cachito"
            nexus_pass = "cachito"
            r = requests.get(
                service["url"] + "/service/rest/v1/repositories",
                auth=(nexus_user, nexus_pass),
            )
            if r.status_code != 200:
                logger.fatal(
                    f"Invalid credentials. Error connecting to Nexus: {r.status_code}"
                )
                exit(1)

        # Cachito
        if f"{podman_project_name}_cachito-api_1" in container["Names"]:
            if container["State"] != "running":
                logger.fatal("Cachito is not running")
                exit(1)
            service["port"] = {
                "host": container["Ports"][0]["host_port"],
                "container": container["Ports"][0]["container_port"],
            }
            service["url"] = f"http://localhost:{service['port']['host']}"
            r = requests.get(service["url"] + "/api/v1/status/short")
            if r.status_code != 200:
                logger.fatal(f"Error connecting to Cachito: {r.status_code}")
                exit(1)
            services["cachito"] = service
    return services


@click.command()
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
def cmd_status(clone_path):
    """Show the status of the Cachito server"""
    clone_path_abs = os.path.abspath(clone_path)

    # Basic checks
    _check_dependencies()
    if not _cachito_repo_exists(clone_path_abs):
        logger.error("Cachito repository does not exist")
        exit(1)

    logger.info("Retrieving Cachito server containers list")
    services = get_services(clone_path_abs)

    # Print status
    print("All services are operational")
    print(f"  Athens  : {services['athens']['url']}")
    print(f"  Nexus   : {services['nexus']['url']}")
    print(f"  Cachito : {services['cachito']['url']}")
    print("")


# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_server = click.Group("server", help="Cachito server commands")
    cmd_server.add_command(name="deploy", cmd=cmd_deploy)
    cmd_server.add_command(name="stop", cmd=cmd_stop)
    cmd_server.add_command(name="status", cmd=cmd_status)
    cli.add_command(cmd_server)
