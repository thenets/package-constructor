import logging
import subprocess
import os
import json
import requests
import datetime
import time

def _setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s", datefmt="%H:%M:%S"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.debug("- Starting Cachito CLI -")
    logger.debug(f"{datetime.datetime.now().strftime('%Y-%m-%d')}")
    return logger


logger = _setup_logger()


def get_global() -> dict:
    return {"cachito_git_url": "https://github.com/containerbuildsystem/cachito"}


def get_logger() -> logging.Logger:
    """Return the logger"""
    return logger


def cmd_log(cmd: list, cwd: str = None) -> None:
    """Log a command to stdout"""
    out = "Run command:\n"
    if cwd:
        out += "├─ 🖥️  $ cd " + cwd + "\n"
    out += "├─ 🖥️  $ " + " ".join(map(str, cmd))
    logger.debug(out)


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

    # Try to retrieve endpoints data
    # - Capture all requests exceptions (timeout and rc != 200)
    # - Exit if it fails
    total_retries = 10
    sleep_time_seconds = 5
    retries = 0
    while retries != total_retries:
        try:
            containers = json.loads(cmd_out.stdout)
            for container in containers:
                service = {}
                service['container_name'] = container["Names"][0]

                # Athens
                if f"{podman_project_name}_athens_1" in service['container_name']:
                    if container["State"] != "running":
                        logger.error("Athens is not running")
                        exit(1)
                    service["port"] = {
                        "host": container["Ports"][0]["host_port"],
                        "container": container["Ports"][0]["container_port"],
                    }
                    service["url"] = f"http://localhost:{service['port']['host']}"
                    r = requests.get(service["url"] + "/healthz")
                    if r.status_code != 200:
                        logger.error(f"Error connecting to Athens: {r.status_code}")
                        exit(1)
                    services["athens"] = service

                # Nexus
                if f"{podman_project_name}_nexus_1" in service['container_name']:
                    if container["State"] != "running":
                        logger.error("Nexus is not running")
                        exit(1)
                    service["port"] = {
                        "host": container["Ports"][0]["host_port"],
                        "container": container["Ports"][0]["container_port"],
                    }
                    service["url"] = f"http://localhost:{service['port']['host']}"
                    r = requests.get(service["url"])
                    if r.status_code != 200:
                        logger.error(f"Error connecting to Nexus: {r.status_code}")
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
                        logger.error(
                            f"Invalid credentials. Error connecting to Nexus: {r.status_code}"
                        )
                        exit(1)

                # Cachito
                if f"{podman_project_name}_cachito-api_1" in service['container_name']:
                    if container["State"] != "running":
                        logger.error("Cachito is not running")
                        exit(1)
                    service["port"] = {
                        "host": container["Ports"][0]["host_port"],
                        "container": container["Ports"][0]["container_port"],
                    }
                    service["url"] = f"http://localhost:{service['port']['host']}"
                    r = requests.get(service["url"] + "/api/v1/status/short")
                    if r.status_code != 200:
                        logger.error(f"Error connecting to Cachito: {r.status_code}")
                        exit(1)
                    services["cachito"] = service
            break

        # Except ConnectionError
        except:
            retries += 1
            logger.warning(f"Failed {retries}/{total_retries}. Retrying in {sleep_time_seconds} seconds")
            time.sleep(sleep_time_seconds)

    if retries == 0:
        logger.fatal("All retries failed. Services are not available")
        exit(1)

    return services
