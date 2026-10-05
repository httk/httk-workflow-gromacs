"""Shared test configuration: isolate the httk configuration of every test."""

import os
import shlex
import shutil
from pathlib import Path

import pytest

# Keep each BLAS/OpenMP runtime of the many short-lived runner processes to one
# thread; child runners and gmx inherit this.
for _thread_limit in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_limit] = "1"


@pytest.fixture(autouse=True)
def _isolated_httk_config(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every test its own httk config and data home, so no workspace registry leaks between tests."""

    monkeypatch.setenv("HTTK_CONFIG_HOME", str(tmp_path_factory.mktemp("httk-config")))
    monkeypatch.setenv("HTTK_DATA_HOME", str(tmp_path_factory.mktemp("httk-store")))
    # A developer's launch prefix must not leak into the tests.
    monkeypatch.delenv("HTTK_WORKFLOW_LAUNCH", raising=False)


DATA = Path(__file__).resolve().parent / "data"
REPO_ROOT = Path(__file__).resolve().parent.parent


def gmx_command() -> list[str] | None:
    """The real ``gmx`` command: ``HTTK_TEST_GROMACS_COMMAND``, else ``gmx`` on PATH, else ``None``."""

    command = os.environ.get("HTTK_TEST_GROMACS_COMMAND") or shutil.which("gmx")
    return shlex.split(command) if command else None


requires_gmx = pytest.mark.skipif(
    gmx_command() is None, reason="needs a real gmx: set HTTK_TEST_GROMACS_COMMAND or put gmx on PATH"
)
