import pytest
from click.testing import CliRunner

import cli_server
import common


@pytest.fixture(scope="session", autouse=True)
def disable_logging():
    logger = common.get_logger()
    logger.disabled = True


@pytest.fixture
def cachito_repo_path():
    return common.get_cachito_repository_path()


@pytest.fixture(scope="session")
def runner():
    return CliRunner()


@pytest.fixture(scope="class")
def server(runner):
    # Start
    result = runner.invoke(cli_server.cmd_start, [])
    assert result.exit_code == 0
    assert "All services are operational" in result.output

    yield

    # Stop
    result = runner.invoke(cli_server.cmd_stop, [])
    assert result.exit_code == 0
    assert "Cachito server stopped" in result.output
