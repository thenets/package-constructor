import os

import click

import cli_builder
import cli_server
import helpers

_global = helpers.get_global()
logger = helpers.get_logger()


def _check_dependencies():
    # Check podman
    if not helpers.check_executable("podman"):
        logger.error("podman is not available in the PATH")
        exit(1)


def _check_requirements_file_output(requirements_out) -> None:
    if requirements_out[0] != "/":
        requirements_out = os.path.join(os.getcwd(), requirements_out)

    try:
        os.path.dirname(requirements_out)
        if not os.path.isdir(os.path.dirname(requirements_out)):
            exit(1)

    except:
        logger.error("Parent directory of requirements-out.txt does not exist")
        logger.error(f"Parent directory: {os.path.dirname(requirements_out)}")
        exit(1)


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
    if not helpers.cachito_repo_exists(clone_path_abs):
        logger.error("Cachito repository does not exist")
        exit(1)

    # Print status
    logger.info("Retrieving Cachito server containers list")
    is_running = helpers.is_running(clone_path_abs)
    if is_running:
        print("All services are operational")
    else:
        print("Some services are not operational")


@click.command()
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
@click.option(
    "--requirements-in",
    "-i",
    default="./requirements-in.txt",
    help="Path to the input requirements file",
)
@click.option(
    "--requirements-out",
    "-o",
    default="./requirements-out.txt",
    help="Path to the output requirements file",
)
@click.option(
    "--restart-server",
    "-r",
    is_flag=True,
    help="Restart the Cachito server to clean the cache",
)
def cmd_extract_dependencies(
    clone_path, requirements_in, requirements_out, restart_server
):
    """From requirements-in.txt, extract the dependencies and write them to requirements-out.txt"""
    clone_path_abs = os.path.abspath(clone_path)
    pip_cache_dir = os.path.join(helpers.get_cache_dir(), "pip-extract")

    # Basic checks
    if not os.path.isfile(requirements_in):
        logger.error("requirements-in.txt does not exist")
        exit(1)
    _check_dependencies()
    if not helpers.cachito_repo_exists(clone_path_abs):
        logger.error("Cachito repository does not exist")
        exit(1)

    # Start or restart the services
    if restart_server:
        cli_server.restart(clone_path_abs)
    else:
        if not helpers.is_running(clone_path_abs):
            cli_server.start(clone_path_abs)

    # Create a Containerfile with the cachito proxy
    logger.info("Creating Containerfile")
    containerfile_path = os.path.join(pip_cache_dir, "Containerfile")
    with open(containerfile_path, "w") as f:
        f.write(
            """FROM registry-proxy.engineering.redhat.com/rh-osbs/ansible-automation-platform-24-ee-minimal-rhel9:1.0.0-371
# USER root
ADD ./requirements-in.txt /build/requirements-in.txt

#<cachito-disable> BEGIN
RUN set -x \
    && echo "nameserver 1.1.1.1" > /etc/resolv.conf \
    && echo "nameserver 8.8.8.8" > /etc/resolv.conf
#<cachito-disable> END

#<cachito-proxy> BEGIN
#RUN set -x \
#    && rm -f /etc/resolv.conf
ENV PIP_NO_BINARY=:all:

ENV GOPROXY=http://host.containers.internal:3000
ENV PIP_TRUSTED_HOST=host.containers.internal:8082
ENV PIP_INDEX=http://cachito:cachito@host.containers.internal:8082/repository/cachito-pip-proxy/pypi
ENV PIP_INDEX_URL=http://cachito:cachito@host.containers.internal:8082/repository/cachito-pip-proxy/simple
#<cachito-proxy> END

# RUN pip install -U pip setuptools

RUN set -x \
    && mkdir -p /build \
    && pip install -vvvv -r /build/requirements-in.txt \
    && pip freeze > /build/requirements-out.txt
"""
        )
    logger.info("Copying requirements-in.txt to the cache dir")
    requirements_in_abs = os.path.abspath(requirements_in)
    requirements_in_cache = os.path.join(pip_cache_dir, "requirements-in.txt")
    os.makedirs(pip_cache_dir, exist_ok=True)
    helpers.run(["cp", requirements_in_abs, requirements_in_cache])

    logger.info("Building the container (no dns)")
    cmd = [
        "podman",
        "build",
        "-f",
        os.path.join(pip_cache_dir, "Containerfile"),
        "--no-cache",
        "--dns",
        "none",
        pip_cache_dir,
    ]
    helpers.cmd_log(
        cmd,
        cwd=pip_cache_dir,
    )
    os.system(" ".join(cmd))

    cli_builder.dump_dependencies_from_cachito_pip_proxy_to_file(
        clone_path, requirements_out
    )


@click.command()
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
@click.option(
    "--requirements-out",
    "-o",
    required=True,
    help="Path to the output requirements file",
)
def cmd_debug_proxy(clone_path, requirements_out):
    """From requirements-in.txt, extract the dependencies and write them to requirements-out.txt"""
    os.path.abspath(clone_path)

    _check_requirements_file_output(requirements_out)

    cli_builder.dump_dependencies_from_cachito_pip_proxy_to_file(
        clone_path, requirements_out
    )


# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_pip = click.Group("pip", help="Pip server commands")
    cmd_pip.add_command(name="status", cmd=cmd_status)
    cmd_pip.add_command(name="extract-dependencies", cmd=cmd_extract_dependencies)
    cmd_pip.add_command(name="debug-proxy", cmd=cmd_debug_proxy)
    cli.add_command(cmd_pip)
