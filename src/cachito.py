# %% Import libs
from pprint import pprint as pp
import requests
import click
import json as json_lib
import base64
import os
import sys

# %% Setup session
requests_s = requests.Session()
requests_s.verify = False
requests.packages.urllib3.disable_warnings()

# %% Main vars
cachito_url = None
nexus_url = None
cert_url = None

def validate_vars():
    if not cachito_url:
        print("CACHITO_URL is not set")
        sys.exit(1)
    if not nexus_url:
        print("NEXUS_URL is not set")
        sys.exit(1)
    if not cert_url:
        print("CERT_URL is not set")
        sys.exit(1)


# %% Helpers
def replace_content(content: str):
    # Do transformations here...
    return content


def get_request(*args, **kwargs):
    """Get request and replace content"""
    request = requests_s.get(*args, **kwargs)
    try:
        # Get json
        j_obj = request.json()
        j_str = json_lib.dumps(j_obj, indent=4, sort_keys=True)
        # Replace
        j_str = replace_content(j_str)
        json_obj = json_lib.loads(j_str)
    except json_lib.decoder.JSONDecodeError:
        json_obj = {}
    text = replace_content(request.text)
    return (request, text, json_obj)


def post_request(*args, **kwargs):
    """Post request and replace content"""
    request = requests.post(*args, **kwargs)
    try:
        # Get json
        j_obj = request.json()
        j_str = json_lib.dumps(j_obj, indent=4, sort_keys=True)
        # Replace
        j_str = replace_content(j_str)
        json_obj = json_lib.loads(j_str)
    except json_lib.decoder.JSONDecodeError:
        json_obj = {}
    text = replace_content(request.text)
    return (request, text, json_obj)


def print_json(j):
    print(json_lib.dumps(j, indent=4, sort_keys=True))


# %% CLI


@click.command()
@click.option("--repo", default=None, help="Repository URL")
@click.option("--json", default=False, is_flag=True, help="Print JSON")
def list(repo, json):
    """List requests"""
    if repo:
        r, t, j = get_request(f"{cachito_url}/requests", params={"repo": repo})
    else:
        r, t, j = get_request(f"{cachito_url}/requests")

    if json:
        print_json(j)
    else:
        # Print table with: items[*][id,pkg_managers,state,repo]
        print("ID\tState\t\tType\tRepo")
        for item in j["items"]:
            _tmp_pkg_managers = ",".join(item["pkg_managers"])
            print(
                f"{item['id']}\t{item['state'].ljust(8)}\t{_tmp_pkg_managers}\t{item['repo']}"
            )


@click.command()
@click.argument("request_id", type=int)
@click.option("--json", default=False, is_flag=True, help="Print JSON")
def describe(request_id, json):
    """Describe a request"""
    r, t, j = get_request(f"{cachito_url}/requests/{request_id}")
    if json:
        print_json(j)
    else:
        try:
            # Print details of request
            print(f"ID: {j['id']}")
            print(f"State: {j['state']}")
            print(f"Repo: {j['repo']}")
            print(f"Ref: {j['ref']}")
            print(f"Package manager: {j['pkg_managers']}")
            print(f"Dependencies:")
            for dep in j["dependencies"]:
                print(f"  {dep['type']}: {dep['name']}=={dep['version']}")
            print(f"Environment variables: {j['environment_variables']}")
            print(f"Flags: {j['flags']}")
            print(f"User: {j['user']}")
        except:
            print_json(j)


@click.command()
@click.argument("request_id", type=int)
def logs(request_id):
    """Log of a request"""
    r, t, j = get_request(f"{cachito_url}/requests/{request_id}/logs")
    print(t)


@click.command()
@click.argument("request_id", type=int)
@click.option("--json", default=False, is_flag=True, help="Print JSON")
def configuration_files(request_id, json):
    """Configuration files of a request"""
    r, t, j = get_request(f"{cachito_url}/requests/{request_id}/configuration-files")
    if json:
        print_json(j)
    else:
        try:
            # For each item, print type, path, content
            for item in j:
                _tmp_content_decoded = replace_content(
                    base64.b64decode(item["content"]).decode("utf-8")
                )
                print(f"- File: {item['path']}")
                print("  Content:")
                # 2 spaces padding for each line
                print("    - " + _tmp_content_decoded.replace("\n", "\n    - "))
        except:
            print_json(j)


@click.command()
@click.option("--repo", required=True, help="Repository URL")
@click.option("--ref", required=True, help="Repository reference")
@click.option(
    "--pkg-manager",
    required=True,
    help="Package manager",
    type=click.Choice(["gomod", "npm", "pip", "git-submodule", "yarn", "rubygems"]),
)
@click.option("--json", default=False, is_flag=True, help="Print JSON")
def new(repo, ref, pkg_manager, json):
    """Create a new request"""

    # Packages
    # swich case for [pip, gomod]
    if pkg_manager == "pip":
        packages = {"pip": [{"path": "."}]}
    elif pkg_manager == "gomod":
        packages = {"gomod": [{"path": "."}]}
    else:
        raise Exception("Not implemented")

    # Send JSON data
    r, t, j = post_request(
        f"{cachito_url}/requests",
        json={
            "repo": repo,
            "ref": ref,
            "pkg_managers": [pkg_manager],
            "packages": packages,
        },
    )
    if json:
        print_json(j)
    else:
        try:
            # Print details of request
            print(f"ID: {j['id']}")
            print(f"State: {j['state']}")
            print(f"Repo: {j['repo']}")
        except:
            print_json(j)


@click.command()
@click.argument("request_id", type=int, required=True)
@click.argument("output_dir", type=click.Path(exists=True), required=True)
def download(request_id, output_dir):
    """Download a request"""
    import os
    import sys
    import tarfile

    _abs_output = os.path.abspath(output_dir)

    # fail if output dir is not empty
    if os.path.exists(_abs_output) and os.listdir(_abs_output):
        print(f"Error: Output directory '{_abs_output}' is not empty")
        sys.exit(1)

    print(f"Downloading to {_abs_output}")
    r = requests_s.get(f"{cachito_url}/requests/{request_id}/download", stream=True)
    print(f"url: {r.url}")
    if r.status_code == 200:
        import tempfile

        _tmp_tar_gz_file = tempfile.NamedTemporaryFile()
        with open(_tmp_tar_gz_file.name, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024):
                f.write(chunk)
        tar = tarfile.open(_tmp_tar_gz_file.name, "r:gz")
        tar.extractall(path=_abs_output)
        tar.close()
    else:
        print(f"Error downloading request {request_id}")

    if cert_url:
        print("Downloading the 'cert' file")
        _cert_r = requests_s.get(cert_url, stream=True)
        if _cert_r.status_code == 200:
            with open(os.path.join(_abs_output, "package-index-ca.pem"), "wb") as f:
                for chunk in _cert_r.iter_content(chunk_size=1024):
                    f.write(chunk)
            # print("Done")

    print("Generating the 'cachito.env' file")
    _describe_r, _, _describe_j = get_request(f"{cachito_url}/requests/{request_id}")
    if _describe_r.status_code == 200:
        pip_index_url = _describe_j["environment_variables"]["PIP_INDEX_URL"]

        _cachito_env_content = "#!/bin/bash\n"
        _cachito_env_content += f"export PIP_INDEX_URL={pip_index_url}\n"
        if cert_url:
            _cachito_env_content += (
                f"export PIP_CERT={os.path.join('/cachito/', 'package-index-ca.pem')}\n"
            )
        _cachito_env_content += (
            f"export PIP_TRUSTED_HOST={pip_index_url.split('/')[2].split('@')[1]}\n"
        )

        with open(os.path.join(_abs_output, "cachito.env"), "w") as f:
            f.write(_cachito_env_content)

        # print("Done")
    else:
        print(f"Error generating 'cachito.env' file")


# Sonatype Nexus
# --------------------
def nexus_auth():
    # import HTTPBasicAuth
    from requests.auth import HTTPBasicAuth

    # Get credentials from env vars
    _user = os.getenv("NEXUS_USER")
    _pass = os.getenv("NEXUS_PASS")

    if _user is None or _pass is None:
        print("Error: NEXUS_USER or NEXUS_PASS not set")
        sys.exit(1)

    return HTTPBasicAuth(_user, _pass)


@click.command()
@click.option("--json", default=False, is_flag=True, help="Print JSON")
def list_repos(json):
    """List Nexus repositories"""
    # import HTTPBasicAuth
    from requests.auth import HTTPBasicAuth

    r = requests.get(
        f"{nexus_url}/service/rest/v1/repositories",
        auth=nexus_auth(),
    )
    if r.status_code == 200:
        if json:
            print_json(r.json())
        else:
            print("Repositories:")
            for item in r.json():
                print(f"  - {item['name']}")
    else:
        print(f"Error: {r.status_code}")


@click.command()
@click.argument("repo_name", type=str, required=True)
@click.option("--json", default=False, is_flag=True, help="Print JSON")
def list_components(repo_name, json):
    """List components in a Nexus repository"""
    # import HTTPBasicAuth
    from requests.auth import HTTPBasicAuth

    def _pag_request(cont_token=None):
        params = {
            "repository": repo_name,
        }
        if cont_token:
            params.update({"continuationToken": cont_token})
        r = requests.get(
            f"{nexus_url}/service/rest/v1/components",
            params=params,
            auth=nexus_auth(),
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
        print_json(full_items)
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
def describe_repo(repo_name, json):
    """List packages in a Nexus repository"""
    # import HTTPBasicAuth
    from requests.auth import HTTPBasicAuth

    r = requests.get(
        f"{nexus_url}/service/rest/v1/repositories/{repo_name}/",
        auth=nexus_auth(),
    )
    if r.status_code == 200:
        if json:
            print_json(r.json())
        else:
            print(f"Repository: {repo_name}")
            item = r.json()
            print(f"  - Name: {item['name']}")
            print(f"  - Type: {item['type']}")
            print(f"  - URL : {item['url']}")
    else:
        print(f"Error: {r.status_code}")


# main
# --------------------
if __name__ == "__main__":

    @click.group()
    def cli():
        pass

    @click.group()
    def request():
        pass

    cli.add_command(request)
    request.add_command(list)
    request.add_command(describe)
    request.add_command(logs)
    request.add_command(configuration_files)
    request.add_command(new)
    request.add_command(download)

    @click.group()
    def nexus():
        pass

    cli.add_command(nexus)
    nexus.add_command(list_repos)
    nexus.add_command(list_components)
    nexus.add_command(describe_repo)

    cli()
