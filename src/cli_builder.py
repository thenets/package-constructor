import os

import click
import jinja2

import common

_global = common.get_global()
logger = common.get_logger()


def _new_template_interceptor(container_file_path: str, services: dict) -> str:
    """Intercept the Containerfile and create a new one with the Cachito instructions.

    Returns:
        str: The path to the new Containerfile
    """

    # Check if '#<cachito-env>' is present
    container_file_content = ""
    with open(container_file_path, "r") as f:
        container_file_content = f.read()

    # Check for "#<cachito-disable>" and "#<cachito-proxy>"
    lines = container_file_content.splitlines()
    cachito_disable_index = -1
    cachito_proxy_index = -1
    for i, line in enumerate(lines):
        line_clean = line.strip().replace(" ", "")
        if "#<cachito-disable>" in line_clean:
            cachito_disable_index = i
        if "#<cachito-proxy>" in line_clean:
            cachito_proxy_index = i
    if cachito_disable_index == -1:
        logger.fatal(
            "Cachito instructions not found in Containerfile. Aborting\n"
            "├─ Please add the following line to your Containerfile:\n"
            "├─ #<cachito-disable>"
        )
        exit(1)
    if cachito_proxy_index == -1:
        logger.fatal(
            "Cachito instructions not found in Containerfile. Aborting\n"
            "├─ Please add the following line to your Containerfile:\n"
            "├─ #<cachito-proxy>"
        )
        exit(1)

    if cachito_disable_index > cachito_proxy_index:
        logger.fatal(
            "The '#<cachito-disable>' instruction must be before the '#<cachito-proxy>' instruction. Aborting"
        )
        exit(1)

    # Create the template data
    template_data = {
        "container_file_content_before_disable": "\n".join(
            lines[:cachito_disable_index]
        ),
        "container_file_content_after_disable": "\n".join(
            lines[cachito_disable_index + 1 : cachito_proxy_index]
        ),
        "container_file_content_after_proxy": "\n".join(
            lines[cachito_proxy_index + 1 :]
        ),
    }
    template_data["custom_envs"] = {}
    for service in services.values():
        if "custom_envs" in service.keys():
            template_data["custom_envs"].update(service["custom_envs"])

    # Generate the new Containerfile
    template_string = """
{{ container_file_content_before_disable }}
#<cachito-disable> BEGIN
RUN set -x \\
    && echo "nameserver 1.1.1.1" > /etc/resolv.conf \\
    && echo "nameserver 8.8.8.8" > /etc/resolv.conf
#<cachito-disable> END
{{ container_file_content_after_disable }}
#<cachito-proxy> BEGIN
RUN set -x \\
    && rm -f /etc/resolv.conf
ENV PIP_NO_BINARY=:all:
{% for k, v in custom_envs.items() %}
ENV {{ k }}={{ v }}
{%- endfor %}
#<cachito-proxy> END
{{ container_file_content_after_proxy }}
"""
    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader("."), autoescape=True
    )
    template = template_env.from_string(template_string)
    template_result = template.render(template_data)

    # Add new proxies to template_result
    # TODO create new proxies instead of using the "cachito-pip-proxy"
    template_result = template_result.replace("<PIP_REPO_NAME>", "cachito-pip-proxy")

    # Write the new Containerfile
    new_containerfile_path = os.path.abspath(
        os.path.join(os.path.dirname(container_file_path), "cachito.containerfile")
    )
    logger.info("Writing new Containerfile to: " + new_containerfile_path)
    with open(new_containerfile_path, "w") as f:
        f.write(template_result)

    return new_containerfile_path


def _build_validate(file, build_context):
    """Validate the build parameters"""

    # Check if Containerfile exists
    if not os.path.isfile(file):
        logger.error("Containerfile not found: " + file)
        exit(1)

    # Check if build context exists
    if build_context:
        if not os.path.isdir(build_context):
            logger.error("Build context not found: " + build_context)
            exit(1)
    else:
        build_context = os.path.dirname(os.path.abspath(file))


def _create_python_requirements_file(file_abs: str, repo_data: dict) -> None:
    def _generate_python_requirements_file(
        repo_data: dict,
        python_requirements_file_path: str,
    ) -> None:
        """Generate a requirements.txt file for a Python project"""
        dependencies_list = []
        for dependency in repo_data["dependencies"]:
            if dependency["format"] == "pypi":
                dependencies_list.append(
                    f"{dependency['name']}=={dependency['version']}"
                )
        dependencies_list.sort()

        out = ""
        for dependency in dependencies_list:
            out += f"{dependency}\n"
        with open(python_requirements_file_path, "w") as f:
            f.write(out)

    if os.path.isdir(file_abs):
        python_requirements_file_path = os.path.abspath(
            os.path.join(os.path.dirname(file_abs), "requirements.txt")
        )
    else:
        python_requirements_file_path = file_abs
    logger.info("Retrieving: " + python_requirements_file_path)
    _generate_python_requirements_file(repo_data, python_requirements_file_path)


def dump_dependencies_from_cachito_pip_proxy_to_file(
    cachito_repo_path: str,
    requirements_out: str,
):
    """Dump the dependencies list from the Cachito pip proxy repo to a file"""
    services = common.get_services(cachito_repo_path)
    repo_data = common._nexus_get_repo_data(services, "cachito-pip-proxy")
    _create_python_requirements_file(requirements_out, repo_data)


@click.command()
@click.option(
    "--clone-path",
    "-p",
    default=os.getcwd() + "/cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
@click.option(
    "--file",
    "-f",
    default="./Containerfile",
    help="Path to the Containerfile to build",
)
@click.option(
    "--build-context",
    "-c",
    help="Path to the build context. Defaults to the directory of the Containerfile",
)
@click.option("--tag", "-t", required=True, help="Tag to apply to the built image")
@click.option(
    "--no-cache",
    is_flag=True,
    default=False,
    help="Do not use cache when building the container image (default: False)",
)
def cmd_build(clone_path, file, build_context, tag, no_cache):
    """Build a container image using Cachito servers"""
    _build_validate(file, build_context)

    additional_args = []
    if no_cache:
        additional_args.append("--no-cache")

    services = common.get_services(clone_path)
    networks = [service["network"] for service in services.values()]
    if len(set(networks)) != 1:
        logger.error("All services must use the same network")
        exit(1)

    file_abs = os.path.abspath(file)
    if build_context:
        build_context_abs = os.path.abspath(build_context)
    else:
        build_context_abs = os.path.dirname(file_abs)

    new_file_abs = _new_template_interceptor(file_abs, services)

    try:
        command = (
            [
                "podman",
                "build",
                "-f",
                new_file_abs,
                "--dns",
                "none",
            ]
            + additional_args
            + [
                "-t",
                tag,
                build_context_abs,
            ]
        )
        common.cmd_log(command)
        rc = os.system(" ".join(command))
        if rc != 0:
            raise Exception(f"Return code: {rc}")

    except Exception as e:
        logger.error("Error building image. Aborting")
        logger.error(e)
        exit(1)

    logger.info("Image built successfully")

    # TODO create new proxies instead of using the "cachito-pip-proxy"
    repo_data = common._nexus_get_repo_data(services, "cachito-pip-proxy")

    _create_python_requirements_file(file_abs, repo_data)


@click.command()
@click.option(
    "--clone-path",
    "-p",
    default=os.getcwd() + "/cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
@click.option(
    "--file",
    "-f",
    default="./Containerfile",
    help="Path to the Containerfile to build",
)
@click.option(
    "--build-context",
    "-c",
    help="Path to the build context. Defaults to the directory of the Containerfile",
)
def cmd_get_dependencies(clone_path, file, build_context):
    """Get the dependencies files for a container build"""
    _build_validate(file, build_context)

    services = common.get_services(clone_path)
    # TODO create new proxies instead of using the "cachito-pip-proxy"
    repo_data = common._nexus_get_repo_data(services, "cachito-pip-proxy")
    file_abs = os.path.abspath(file)

    _create_python_requirements_file(file_abs, repo_data)


# cmd_pip_generate
# Params: requirements_file_in, requirements_file_out
@click.command()
@click.option(
    "--requirements-file-in",
    "-i",
    default="./requirements.txt",
    help="Path to the requirements file to be processed",
)
@click.option(
    "--requirements-file-out",
    "-o",
    default="./requirements-cachito.txt",
    help="Path to the requirements file to be generated",
)
def cmd_pip_generate(requirements_file_in, requirements_file_out):
    """Reads a requirements.txt file and generates a requirements-cachito.txt file
    with all the indirect dependencies of the requirements.txt file.
    """
    import cli_server

    # Check if server is running, start OR restart if needed
    cli_server._check_dependencies()

    requirements_file_in_abs = os.path.abspath(requirements_file_in)
    requirements_file_out_abs = os.path.abspath(requirements_file_out)

    if not os.path.isfile(requirements_file_in_abs):
        logger.error("requirements_file_in not found: " + requirements_file_in_abs)
        exit(1)

    # TODO create new proxies instead of using the "cachito-pip-proxy"
    repo_data = common._nexus_get_repo_data({}, "cachito-pip-proxy")

    dependencies_list = []
    for dependency in repo_data["dependencies"]:
        if dependency["format"] == "pypi":
            dependencies_list.append(f"{dependency['name']}=={dependency['version']}")
    dependencies_list.sort()

    out = ""
    for dependency in dependencies_list:
        out += f"{dependency}\n"
    with open(requirements_file_out_abs, "w") as f:
        f.write(out)


class Builder:
    config = None

    def __init__(self, config_file_path: str):
        self._load_config(config_file_path)

        # Create the workdir
        os.makedirs(self.config.workdir.path, exist_ok=True)

    def _load_config(self, config_file_path: str):
        """Load the config file and validate it"""
        self.config_file_path = config_file_path
        if not os.path.isfile(config_file_path):
            logger.error("Config file not found: " + config_file_path)
            exit(1)
        with open(config_file_path, "r") as f:
            config_file_content = f.read()
            import yaml

            config_data = yaml.safe_load(config_file_content)
        if not self._is_config_file_valid(config_data):
            logger.error("Config file is not valid: " + config_file_path)
            exit(1)
        self.config = common.dotdict(config_data)

        # Workdir must be an absolute path
        if self.config.workdir.path.startswith("/"):
            self.config.workdir.path = self.config.workdir.path.path
        else:
            _tmp_path = os.path.join(
                os.path.dirname(self.config_file_path),
                self.config.workdir.path,
            )
            self.config.workdir.path = os.path.abspath(_tmp_path)

    def _is_config_file_valid(self, config: dict):
        """Validate the config file"""
        from schema import And, Optional, Schema, SchemaError

        def _is_url(s):
            """Validates URL format"""
            import re

            match = "^https?:\/\/.*$"
            return bool(re.match(match, s))

        def _validate_name_n_version(s):
            """Validates name and version"""
            import re

            # format: <name>==<num>.<num>.<num>
            match = "^[a-zA-Z0-9\.\-_]+==[0-9]+\.[0-9]+\.[0-9]+$"
            return bool(re.match(match, s))

        schema_template = Schema(
            {
                "kind": And(
                    str,
                    lambda s: s in ("container"),
                    error="Invalid kind. Valid values: [container]",
                ),
                "workdir": {
                    "path": And(str, len, error="Invalid path."),
                },
                "packageManagers": {
                    Optional("ansible"): {
                        Optional("collections"): [
                            And(
                                str,
                                len,
                                _validate_name_n_version,
                                error="Invalid name and version format. Valid example: community-general==6.2.0",
                            )
                        ],
                        Optional("roles"): [
                            And(
                                str,
                                len,
                                _validate_name_n_version,
                                error="Invalid name and version format. Valid example: cloudalchemy.node_exporter==2.0.0",
                            )
                        ],
                    },
                    Optional("python"): {
                        "includeDependencies": And(bool),
                        "dependencies": [
                            And(
                                str,
                                len,
                                _validate_name_n_version,
                                error="Invalid name and version format. Valid example: ansible-core==2.14.11",
                            )
                        ],
                    },
                },
                "sources": [
                    {
                        "kind": And(
                            str,
                            lambda s: s in ("git"),
                            error="Invalid kind. Valid values: [git]",
                        ),
                        "url": And(
                            str,
                            len,
                            _is_url,
                            error="Invalid URL. Valid example: https://github.com/thenets/rinted-container.git",
                        ),
                        "ref": And(str, len, error="Invalid ref."),
                        "path": And(str, len, error="Invalid path."),
                    }
                ],
                "containers": [
                    {
                        "imageName": And(str, len),
                        Optional("containerfilePath"): And(str, len),
                        Optional("containerfileContent"): And(str, len),
                        "restrictions": {
                            "disableDnsResolution": And(bool),
                        },
                        "proxies": {
                            "python": And(bool),
                            "golang": And(bool),
                        },
                        "sources_subpath": And(str, len),
                        "podmanCacheEnabled": And(bool),
                    }
                ],
            }
        )

        try:
            schema_template.validate(config)
        except SchemaError as e:
            logger.error(e)
            return False

        # Must have at one of the following: containerfilePath, containerfileContent
        for container in config["containers"]:
            try:
                path = container["containerfilePath"]
            except:
                path = ""
            try:
                content = container["containerfileContent"]
            except:
                content = ""
            if not path and not content:
                logger.error(f"Container: {container['imageName']}")
                logger.error("├─ ContainerfilePath and containerfileContent not found")
                logger.error("├─ One of the above must be present")
                logger.error("└─ Aborting...")
                exit(1)
            if path and content:
                logger.error(f"Container: {container['imageName']}")
                logger.error("├─ ContainerfilePath and containerfileContent found")
                logger.error("├─ Only one of the above must be present")
                logger.error("└─ Aborting...")
                exit(1)

        # TODO: each container.imageName must be unique

        return True

    def _pull_sources(self):
        pass

    def _build_image(self, container: dict):
        """Build the container image"""
        _containerfile_path = None

        # Pull the base image if content is not present
        if container.containerfilePath:
            _containerfile_path = os.path.join(
                self.config.workdir.path, container.containerfilePath
            )
            # copy
            logger.info("Copying Containerfile: " + _containerfile_path)
            _original_file_path = os.path.join(
                os.path.dirname(self.config_file_path),
                container.containerfilePath,
            )
            common.check_output(["cp", _original_file_path, _containerfile_path])
        else:
            _containerfile_path = os.path.join(
                self.config.workdir.path, "base_image.containerfile"
            )
            logger.info("Creating Containerfile: " + _containerfile_path)
            with open(_containerfile_path, "w") as f:
                f.write(container.containerfileContent)

        # Build the image
        logger.info(f"Building image: {container.imageName}")
        _build_args = []
        if not container.podmanCacheEnabled:
            _build_args.append("--no-cache")
        if container.restrictions.disableDnsResolution:
            _build_args.append("--dns=none")
        common.check_output(
            [
                "podman",
                "build",
            ]
            + _build_args
            + [
                "-f",
                _containerfile_path,
                "-t",
                container.imageName,
                self.config.workdir.path,
            ]
        )

    def build(self):
        self._pull_sources()
        for container in self.config.containers:
            self._build_image(container)

        # Success message
        logger.info("Images built successfully")
        for container in self.config.containers:
            logger.info(f"├─ {container.imageName}")


@click.command()
@click.option(
    "--config-file",
    "-c",
    default="./constructor.yml",
    help="Path to the constructor config file",
)
def cmd_run(config_file):
    """creates a build from a constructor config file"""
    builder = Builder(config_file)
    logger.info("Workdir: " + builder.config.workdir.path)
    builder.build()


# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_server = click.Group("builder", help="Container builder commands")
    cmd_server.add_command(name="run", cmd=cmd_run)
    cli.add_command(cmd_server)
