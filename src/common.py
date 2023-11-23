"""
Helpers

Shared/global functions and variables
"""


import datetime
import json
import logging
import os
import subprocess
import tempfile
import time

import jinja2
import requests

requests_s = requests.Session()
requests_s.verify = False
requests.packages.urllib3.disable_warnings()


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    # Based on https://stackoverflow.com/questions/2352181/how-to-use-a-dot-to-access-members-of-dictionary
    def __init__(self, *args, **kwargs):
        # recursively convert nested dicts
        for arg in args:
            if isinstance(arg, dict):
                pass
                for k, v in arg.items():
                    if isinstance(v, dict):
                        v = dotdict(v)
                    elif isinstance(v, list):
                        for i in range(len(v)):
                            if isinstance(v[i], dict):
                                v[i] = dotdict(v[i])
                    self[k] = v
        if kwargs:
            for k, v in kwargs.items():
                if isinstance(v, dict):
                    v = dotdict(v)
                self[k] = v

    def __getattr__(self, attr):
        # BUG: when the key is not present, it returns None instead of raising an error
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(dotdict, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(dotdict, self).__delitem__(key)
        del self.__dict__[key]


def _setup_logger():
    class ColoredFormatter(logging.Formatter):
        # Based on https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
        grey = "\x1b[38;20m"
        cyan = "\x1b[36;20m"
        green = "\x1b[32;20m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"

        format = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"
        # format = "%(asctime)s %(name)s %(levelname)s %(message)s (%(filename)s:%(lineno)d)"

        FORMATS = {
            logging.DEBUG: green + format + reset,
            logging.INFO: cyan + format + reset,
            logging.WARNING: yellow + format + reset,
            logging.ERROR: red + format + reset,
            logging.CRITICAL: bold_red + format + reset,
        }

        def format(self, record):
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = ColoredFormatter()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.debug("- Starting Cachito CLI -")
    logger.debug(f"{datetime.datetime.now().strftime('%Y-%m-%d')}")
    return logger


logger = _setup_logger()


def get_global() -> dict:
    return {
        "cachito_git_url": "https://github.com/containerbuildsystem/cachito",
        "nexus": {"user": "cachito", "pass": "cachito"},
    }


def print_json(j):
    print(json.dumps(j, indent=4, sort_keys=True))


def _nexus_auth():
    # import HTTPBasicAuth
    from requests.auth import HTTPBasicAuth

    # Get credentials from env vars
    _user = get_global()["nexus"]["user"]
    _pass = get_global()["nexus"]["pass"]

    return HTTPBasicAuth(_user, _pass)


def _nexus_get_repo_data(services: dict, repo_name) -> dict:
    nexus_url = services["nexus"]["url_local"]

    def _pag_request(cont_token=None):
        params = {
            "repository": repo_name,
        }
        if cont_token:
            params.update({"continuationToken": cont_token})
        r = requests.get(
            f"{nexus_url}/service/rest/v1/components",
            params=params,
            auth=_nexus_auth(),
        )
        return r

    out = {}

    # get repo info
    r = requests.get(
        f"{nexus_url}/service/rest/v1/repositories/{repo_name}/",
        auth=_nexus_auth(),
    )
    out.update(r.json())

    # pagination using 'continuationToken'
    dependencies = []
    cont_token = None
    while True:
        r = _pag_request(cont_token)
        if r.status_code == 200:
            dependencies = dependencies + r.json()["items"]
        else:
            print(f"Error: {r.status_code}")
        cont_token = r.json()["continuationToken"]
        if not cont_token:
            break

    out.update({"dependencies": dependencies})

    return out


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


def run(cmd: list, cwd=None, check=True, print_output=False) -> dotdict:
    """Run a command

    Args:
        cmd (list): Command to run
        cwd (str): Current working directory
        check (bool): Raise an exception if the command fails
        print_output (bool): Print the output to stdout and stderr

    Returns:
        dotdict: Dictionary with the following keys:
            - stdout: stdout
            - stderr: stderr
            - exit_code: exit code
    """
    # Based on https://stackoverflow.com/questions/17190221/subprocess-popen-cloning-stdout-and-stderr-both-to-terminal-and-variables/25960956#25960956
    import asyncio
    import io
    import sys
    from subprocess import SubprocessError

    # Maximum number of bytes to read at once from the 'asyncio.subprocess.PIPE'
    _MAX_BUFFER_CHUNK_SIZE = 1024

    async def run_cmd_async(command, cwd=None, check=False, print_output=False):
        stdout_buffer = io.BytesIO()
        stderr_buffer = io.BytesIO()
        process = await asyncio.subprocess.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def write_stdout(print_output: bool = False) -> None:
            assert process.stdout is not None
            while chunk := await process.stdout.read(_MAX_BUFFER_CHUNK_SIZE):
                stdout_buffer.write(chunk)
                if print_output:
                    print(chunk.decode(), end="", flush=True)

        async def write_stderr(print_output: bool = False) -> None:
            assert process.stderr is not None
            while chunk := await process.stderr.read(_MAX_BUFFER_CHUNK_SIZE):
                stderr_buffer.write(chunk)
                if print_output:
                    print(chunk.decode(), file=sys.stderr, end="", flush=True)

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(write_stdout(print_output=print_output))
            task_group.create_task(write_stderr(print_output=print_output))

            exit_code = await process.wait()
            if check and exit_code != 0:
                raise SubprocessError(
                    f"Command '{command}' returned non-zero exit status {exit_code}."
                )

        out = {
            "stdout": stdout_buffer.getvalue().decode(),
            "stderr": stderr_buffer.getvalue().decode(),
            "exit_code": exit_code,
        }

        return dotdict(out)

    cmd_log(cmd, cwd=cwd)
    try:
        out = asyncio.run(run_cmd_async(cmd, cwd=cwd, check=check))
    except subprocess.CalledProcessError as e:
        logger.error(f"CMD: {e.cmd}")
        logger.error(e.stderr.decode("utf-8"))
        exit(1)
    return out


def check_output(args, **kwargs):
    """Run a command and return the output"""
    cmd_log(list(args))
    try:
        out = subprocess.check_output(args, **kwargs)
    except subprocess.CalledProcessError as e:
        logger.error(f"CMD: {e.cmd}")
        exit(1)
    return out


def check_executable(cmd: str) -> bool:
    """Check if a command is available"""
    try:
        # Check if the command is available in the PATH
        subprocess.run(["which", cmd], check=True, stdout=subprocess.DEVNULL)
        return True
    except:
        return False


def run_script(multi_line_script, cwd: str = None) -> None:
    """Run a multi-line bash script

    Args:
        multi_line_script (str|list): Multi-line bash script. If it is a list, it will be joined with "\n"
        cwd (str): Current working directory
    """
    if not multi_line_script or cwd is None:
        logger.error("run_script: multi_line_script or cwd is None")
        exit(1)
    if isinstance(multi_line_script, list):
        multi_line_script = "#!/bin/bash\n\n" + "\n".join(multi_line_script)

    tmp_script_path = tempfile.mktemp()
    with open(tmp_script_path, "w") as f:
        f.write(multi_line_script)

    logger.debug(f"Run script: {tmp_script_path}")
    logger.debug(f"CWD: {cwd}")
    logger.debug(f"Script:\n{multi_line_script}")
    check_output(["chmod", "+x", tmp_script_path])
    check_output(["bash", tmp_script_path], cwd=cwd)


def git_pull(
    url,
    ref,
    path,
):
    """Clone a git repository"""
    if path[0] != "/":
        logger.error("Path must be absolute (starting with /)")
        logger.error(f"Path: {path}")
        exit(1)

    _parent_dir = os.path.dirname(path)
    os.makedirs(_parent_dir, exist_ok=True)
    _command_clone = f"git clone --depth 1 --branch {ref} {url} {path}"
    if os.path.isdir(os.path.join(path, ".git")):
        logger.debug("Git repository identified. Skipping clone")
        _command_clone = ""
    else:
        _command_clone = f"git clone --depth 1 --branch {ref} {url} {path}"
    commands = [
        "set -ex",
        _command_clone,
        # If the repository already exists, force the checkout again
        f"cd {path}",
        f"git checkout {ref}",
        f"git pull origin {ref}",
    ]
    run_script(commands, cwd=_parent_dir)


def create_file_from_template(
    output_path: str, template_string: str, template_data: dict, post_process=None
):
    """Create a file from a template

    Args:
        template_string (str): Template string
        template_data (dict): Template data. Example: {"name": "John"}
        output_path (str): Output file path
        post_process (function): Function to post-process the template result
    """
    # Create the pyproject.toml file
    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader("."), autoescape=False
    )
    template = template_env.from_string(template_string)
    template_result = template.render(template_data)
    if post_process:
        template_result = post_process(template_result)
    _parent_dir = os.path.dirname(output_path)
    os.makedirs(_parent_dir, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(template_result)


def get_services(cachito_repo_path: str):
    """Get the services from the docker-compose.yml file"""
    services = {
        "athens": {},
        "nexus": {},
        "cachito": {},
    }

    # Get data from podman
    podman_project_name = os.path.basename(cachito_repo_path)
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
        cwd=cachito_repo_path,
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
                service["container_name"] = container["Names"][0]
                service["network"] = container["Networks"][0]

                # Athens
                if f"{podman_project_name}_athens_1" in service["container_name"]:
                    if container["State"] != "running":
                        logger.error("Athens is not running")
                        exit(1)
                    service["port"] = {
                        "host": container["Ports"][0]["host_port"],
                        "container": container["Ports"][0]["container_port"],
                    }
                    service[
                        "url"
                    ] = f"http://host.containers.internal:{service['port']['host']}"
                    service["url_local"] = service["url"].replace(
                        "host.containers.internal", "localhost"
                    )
                    r = requests.get(service["url_local"] + "/healthz")
                    if r.status_code != 200:
                        logger.error(f"Error connecting to Athens: {r.status_code}")
                        exit(1)
                    service["custom_envs"] = {
                        "GOPROXY": f"http://host.containers.internal:{service['port']['host']}",
                    }
                    services["athens"] = service

                # Nexus
                if f"{podman_project_name}_nexus_1" in service["container_name"]:
                    if container["State"] != "running":
                        logger.error("Nexus is not running")
                        exit(1)
                    service["port"] = {
                        "host": container["Ports"][0]["host_port"],
                        "container": container["Ports"][0]["container_port"],
                    }
                    service[
                        "url"
                    ] = f"http://host.containers.internal:{service['port']['host']}"
                    service["url_local"] = service["url"].replace(
                        "host.containers.internal", "localhost"
                    )
                    r = requests.get(service["url_local"])
                    if r.status_code != 200:
                        logger.error(f"Error connecting to Nexus: {r.status_code}")
                        exit(1)
                    service["custom_envs"] = {
                        "PIP_TRUSTED_HOST": f"host.containers.internal:{service['port']['host']}",
                        "PIP_INDEX": f"http://cachito:cachito@host.containers.internal:{service['port']['host']}/repository/<PIP_REPO_NAME>/pypi",
                        "PIP_INDEX_URL": f"http://cachito:cachito@host.containers.internal:{service['port']['host']}/repository/<PIP_REPO_NAME>/simple",
                    }
                    services["nexus"] = service
                    # Test nexus credentials
                    nexus_user = "cachito"
                    nexus_pass = "cachito"
                    r = requests.get(
                        service["url_local"] + "/service/rest/v1/repositories",
                        auth=(nexus_user, nexus_pass),
                    )
                    if r.status_code != 200:
                        logger.error(
                            f"Invalid credentials. Error connecting to Nexus: {r.status_code}"
                        )
                        exit(1)

                # Cachito
                if f"{podman_project_name}_cachito-api_1" in service["container_name"]:
                    if container["State"] != "running":
                        logger.error("Cachito is not running")
                        exit(1)
                    service["port"] = {
                        "host": container["Ports"][0]["host_port"],
                        "container": container["Ports"][0]["container_port"],
                    }
                    service[
                        "url"
                    ] = f"http://host.containers.internal:{service['port']['host']}"
                    service["url_local"] = service["url"].replace(
                        "host.containers.internal", "localhost"
                    )
                    r = requests.get(service["url_local"] + "/api/v1/status/short")
                    if r.status_code != 200:
                        logger.error(f"Error connecting to Cachito: {r.status_code}")
                        exit(1)
                    services["cachito"] = service
            break

        # Except ConnectionError
        except:
            retries += 1
            logger.warning(
                f"Failed {retries}/{total_retries}. Retrying in {sleep_time_seconds} seconds"
            )
            time.sleep(sleep_time_seconds)

    if retries == total_retries:
        logger.fatal("All retries failed. Services are not available")
        exit(1)

    return services


def get_cache_dir():
    default_cache_dir = "./cache"
    return os.path.abspath(default_cache_dir)


def get_default_cachito_repo_path():
    default_cachito_repo_path = "./cache/cachito_repo"
    return os.path.abspath(default_cachito_repo_path)


def is_running(cachito_repo_path: str) -> bool:
    """Check if the services are running"""
    services = get_services(cachito_repo_path)
    logger.debug("is_running: Checking services")
    for service_name, service in services.items():
        logger.debug(f"Checking {service_name}")
        if not service:
            logger.warning(f"{service_name} is not running")
            return False
    return True


def cachito_repo_exists(cachito_repo_path: str):
    """Check if the Cachito repository already exists

    Returns:
        bool: True if the Cachito repository already exists
              False if the Cachito repository does not exist but the path is valid
    """
    if not os.path.isdir(os.path.dirname(cachito_repo_path)):
        logger.error(
            "Parent directory does not exist: " + os.path.dirname(cachito_repo_path)
        )
        exit(1)
    if os.path.isdir(cachito_repo_path):
        if os.path.join(cachito_repo_path, ".git"):
            logger.info("Git repository identified. Skipping clone")
        else:
            logger.error("Directory already exists and it is not a git repository")
            exit(1)
        return True
    else:
        return False


def get_cachito_repository_path() -> str:
    """Returns the path where the Cachito repository is located"""
    current_python_file_path = os.path.abspath(__file__)
    return os.path.join(
        os.path.dirname(current_python_file_path), "./../cache/cachito_repo"
    )
