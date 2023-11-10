import pytest
from click.testing import CliRunner

import cli_server
import common

def pytest_addoption(parser):
    parser.addoption(
        '--server-keep-running',
        help='Do not restart or stop the Cachito server',
        action='store_true',
        default=False,
    )

@pytest.fixture(scope="session", autouse=True)
def disable_logging():
    logger = common.get_logger()
    logger.disabled = True


@pytest.fixture(scope="session")
def cachito_repo_path():
    return common.get_cachito_repository_path()


@pytest.fixture(scope="session")
def runner():
    return CliRunner()


@pytest.fixture(scope="session")
def server(request, runner, cachito_repo_path):
    keep_running = request.config.getoption("--server-keep-running")

    if not common.is_running(cachito_repo_path):
        result = runner.invoke(cli_server.cmd_start, [])
        assert result.exit_code == 0
        assert "All services are operational" in result.output

    yield

    if not keep_running:
        result = runner.invoke(cli_server.cmd_stop, [])
        assert result.exit_code == 0
        assert "Cachito server stopped" in result.output
