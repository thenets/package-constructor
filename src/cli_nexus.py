import click
import os
import requests

import helpers


# Sonatype Nexus
# --------------------
def _nexus_auth():
    # import HTTPBasicAuth
    from requests.auth import HTTPBasicAuth

    # Get credentials from env vars
    _user = os.getenv("NEXUS_USER")
    _pass = os.getenv("NEXUS_PASS")

    if _user is None or _pass is None:
        print("Error: NEXUS_USER or NEXUS_PASS not set")
        exit(1)

    return HTTPBasicAuth(_user, _pass)


@click.command()
@click.option("--json", default=False, is_flag=True, help="Print JSON")
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
def cmd_nexus_list_repos(clone_path, json):
    """List Nexus repositories"""
    services = helpers.get_services(clone_path)
    nexus_url = services["nexus"]["url_local"]

    r = requests.get(
        f"{nexus_url}/service/rest/v1/repositories",
        auth=_nexus_auth(),
    )
    if r.status_code == 200:
        if json:
            helpers.print_json(r.json())
        else:
            print("Repositories:")
            for item in r.json():
                print(f"  - {item['name']}")
    else:
        print(f"Error: {r.status_code}")


@click.command()
@click.argument("repo_name", type=str, required=True)
@click.option("--json", default=False, is_flag=True, help="Print JSON")
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
def cmd_nexus_list_components(clone_path, repo_name, json):
    """List components in a Nexus repository"""
    services = helpers.get_services(clone_path)
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

    # pagination using 'continuationToken'
    full_items = []
    cont_token = None
    while True:
        r = _pag_request(cont_token)

        if r.status_code == 200:
            full_items = full_items + r.json()["items"]
        else:
            print(f"Error: {r.status_code}")

        cont_token = r.json()["continuationToken"]

        if not cont_token:
            break

    if json:
        helpers.print_json(full_items)
    else:
        print("Components:")
        components = full_items
        # sort by name
        components = sorted(components, key=lambda k: k["name"])
        for component in components:
            print(f"  - {component['name']}=={component['version']}")


@click.command()
@click.argument("repo_name", type=str, required=True)
@click.option("--json", default=False, is_flag=True, help="Print JSON")
@click.option(
    "--clone-path",
    "-p",
    default="./cache/cachito_repo",
    help="Path where the Cachito repository is located",
)
def cmd_nexus_describe_repo(clone_path, repo_name, json):
    """List packages in a Nexus repository"""
    services = helpers.get_services(clone_path)
    nexus_url = services["nexus"]["url_local"]

    r = requests.get(
        f"{nexus_url}/service/rest/v1/repositories/{repo_name}/",
        auth=_nexus_auth(),
    )
    if r.status_code == 200:
        if json:
            helpers.print_json(r.json())
        else:
            print(f"Repository: {repo_name}")
            item = r.json()
            print(f"  - Name: {item['name']}")
            print(f"  - Type: {item['type']}")
            print(f"  - URL : {item['url']}")
    else:
        print(f"Error: {r.status_code}")


# Click
# ====================
def click_add_group(cli: click.Group) -> None:
    """Add the group to the CLI"""
    cmd_nexus = click.Group("nexus", help="Sonatype Nexus commands")
    cmd_nexus.add_command(name="list-repos", cmd=cmd_nexus_list_repos)
    cmd_nexus.add_command(name="list-components", cmd=cmd_nexus_list_components)
    cmd_nexus.add_command(name="describe-repo", cmd=cmd_nexus_describe_repo)
    cli.add_command(cmd_nexus)
