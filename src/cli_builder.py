import click
import os
import jinja2

import helpers
import common

_global = helpers.get_global()
logger = helpers.get_logger()


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
{% for k, v in custom_envs.items() %}
ENV {{ k }}={{ v }}
{%- endfor %}
#<cachito-proxy> END
{{ container_file_content_after_proxy }}
"""
    template_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
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
        out = ""
        for dependency in repo_data["dependencies"]:
            if dependency["format"] == "pypi":
                out += f"{dependency['name']}=={dependency['version']}\n"
        with open(python_requirements_file_path, "w") as f:
            f.write(out)

    python_requirements_file_path = os.path.abspath(
        os.path.join(os.path.dirname(file_abs), "requirements.txt")
    )
    logger.info("Retrieving: " + python_requirements_file_path)
    _generate_python_requirements_file(repo_data, python_requirements_file_path)

@click.command()
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
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
def cmd_build(clone_path, file, build_context):
    """Build a container image using Cachito servers"""
    _build_validate(file, build_context)

    services = helpers.get_services(clone_path)
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
        command = [
            "podman",
            "build",
            "-f",
            new_file_abs,
            "--dns",
            "none",
            "-t",
            "test",
            build_context_abs,
        ]
        helpers.cmd_log(command)
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
    default="./cache/cachito_repo",
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

    services = helpers.get_services(clone_path)
    # TODO create new proxies instead of using the "cachito-pip-proxy"
    repo_data = common._nexus_get_repo_data(services, "cachito-pip-proxy")
    file_abs = os.path.abspath(file)

    _create_python_requirements_file(file_abs, repo_data)


# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_server = click.Group("builder", help="Container builder commands")
    cmd_server.add_command(name="build", cmd=cmd_build)
    cmd_server.add_command(name="get-dependencies", cmd=cmd_get_dependencies)
    cli.add_command(cmd_server)
