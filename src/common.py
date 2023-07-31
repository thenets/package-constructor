import requests
import os

import helpers

requests_s = requests.Session()
requests_s.verify = False
requests.packages.urllib3.disable_warnings()

_global = helpers.get_global()
logger = helpers.get_logger()


def _nexus_auth():
    # import HTTPBasicAuth
    from requests.auth import HTTPBasicAuth

    # Get credentials from env vars
    _user = helpers.get_global()["nexus"]["user"]
    _pass = helpers.get_global()["nexus"]["pass"]

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
