import click
import helpers
import os
import jinja2


_global = helpers.get_global()
logger = helpers.get_logger()


def _new_template_interceptor(container_file_path:str, services:dict) -> str:
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
        logger.fatal("Cachito instructions not found in Containerfile. Aborting\n"
        "├─ Please add the following line to your Containerfile:\n"
        "├─ #<cachito-disable>")
        exit(1)
    if cachito_proxy_index == -1:
        logger.fatal("Cachito instructions not found in Containerfile. Aborting\n"
        "├─ Please add the following line to your Containerfile:\n"
        "├─ #<cachito-proxy>")
        exit(1)

    if cachito_disable_index > cachito_proxy_index:
        logger.fatal("The '#<cachito-disable>' instruction must be before the '#<cachito-proxy>' instruction. Aborting")
        exit(1)

    # Create the template data
    template_data = {
    "container_file_content_before_disable" : "\n".join(lines[:cachito_disable_index]),
    "container_file_content_after_disable" : "\n".join(lines[cachito_disable_index+1:cachito_proxy_index]),
    "container_file_content_after_proxy" : "\n".join(lines[cachito_proxy_index+1:])
    }
    template_data['custom_envs'] = {}
    for service in services.values():
        if 'custom_envs' in service.keys():
            template_data['custom_envs'].update(service['custom_envs'])


    # Generate the new Containerfile
    template_string = """
{{ container_file_content_before_disable }}
#<cachito-disable> BEGIN
# RUN set -x \\
#     && echo "nameserver 1.1.1.1" > /etc/resolv.conf \\
#     && echo "nameserver 8.8.8.8" > /etc/resolv.conf
#<cachito-disable> END
{{ container_file_content_after_disable }}
#<cachito-proxy> BEGIN
#RUN set -x \\
#    && rm -f /etc/resolv.conf
{% for k, v in custom_envs.items() %}
ENV {{ k }}={{ v }}
{%- endfor %}
#<cachito-proxy> END
{{ container_file_content_after_proxy }}
"""
    template_env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
    template = template_env.from_string(template_string)
    template_result = template.render(template_data)

    # Add new proxies to template_result
    # TODO create new proxies instead of using the "cachito-pip-proxy"
    template_result = template_result.replace("<PIP_REPO_NAME>", "cachito-pip-proxy")


    # Write the new Containerfile
    new_containerfile_path = os.path.abspath(os.path.join(os.path.dirname(container_file_path), "cachito.containerfile"))
    logger.info("Writing new Containerfile to: " + new_containerfile_path)
    with open(new_containerfile_path, "w") as f:
        f.write(template_result)

    return new_containerfile_path


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
    networks = [service['network'] for service in services.values()]
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
        import sys
        stdout = sys.stdout
        cmd_out = helpers.check_output(
        ["podman", "build", "-f", new_file_abs, "-t", "test", build_context_abs], stderr=sys.stderr)
    except:
        logger.error("Error building image. Aborting")
        exit(1)

    logger.info("Image built successfully")






# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_server = click.Group("builder", help="Container builder commands")
    cmd_server.add_command(name="build", cmd=cmd_build)
    cli.add_command(cmd_server)
