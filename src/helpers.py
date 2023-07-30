import logging
import subprocess
import os
import json
import requests


def _setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


logger = _setup_logger()


def get_global() -> dict:
    return {"cachito_git_url": "https://github.com/containerbuildsystem/cachito"}


def get_logger() -> logging.Logger:
    """Return the logger"""
    return logger


def cmd_log(cmd: list, cwd: str = None) -> None:
    """Log a command to stdout"""
    out = ""
    if cwd:
        out += "├─ 🖥️  $ cd " + cwd
    out += "├─ 🖥️  $ " + " ".join(map(str, cmd))
    logging.debug(out)


def run(cmd: list, cwd=None) -> subprocess.CompletedProcess:
    """Run a command"""
    cmd_log(cmd, cwd=cwd)
    out = subprocess.run(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
    )
    return out


def check_executable(cmd: str) -> bool:
    """Check if a command is available"""
    try:
        # Check if the command is available in the PATH
        subprocess.run(["which", cmd], check=True, stdout=subprocess.DEVNULL)
        return True
    except:
        return False


def get_services(repo_path: str):
    """Get the services from the docker-compose.yml file"""
    services = {
        "athens": {},
        "nexus": {},
        "cachito": {},
    }

    # Get data from podman
    podman_project_name = os.path.basename(repo_path)
    cmd_out = run(
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
