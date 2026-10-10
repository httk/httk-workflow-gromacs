"""End to end with the real ``gmx``: install, run, and collect the ``gromacs.run`` workflow.

Runs only with a real ``gmx`` (``HTTK_TEST_GROMACS_COMMAND`` or ``gmx`` on PATH).
The workflow is installed as the ``httk_plugin.toml`` plugin of this repository,
as ``httk plugin install`` does, into the test's isolated data home.
"""

import json
import shlex
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from conftest import DATA, REPO_ROOT, gmx_command, requires_gmx

pytestmark = [requires_gmx, pytest.mark.slow]


@pytest.fixture
def installed_plugin(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    from httk.core.plugins import install_plugin
    from httk.workflow.packages import _reset_plugin_workflow_cache

    source = tmp_path_factory.mktemp("plugin-source") / "httk-workflow-gromacs"
    shutil.copytree(REPO_ROOT / "workflows", source / "workflows", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(REPO_ROOT / "httk_plugin.toml", source)
    install_plugin(source)
    _reset_plugin_workflow_cache()
    yield
    _reset_plugin_workflow_cache()


def test_gromacs_run_minimizes_argon_and_collects_one_run(
    tmp_path: Path, installed_plugin: None, capsys: pytest.CaptureFixture[str]
) -> None:
    store = pytest.importorskip("httk.store")
    from httk.core import DataRecord, Run
    from httk.core.cli import CLIContext
    from httk.workflow import TaskManager, Workspace
    from httk.workflow.collecting import job_records
    from httk.workflow.registry import register_workspace
    from httk.workflow.scaffold import new_job
    from httk.workflow.workflow_cli import command

    from httk.codes.gromacs import parse_mdrun_log

    workspace = Workspace.initialize(tmp_path / "workspace")
    workspace.set_setting("gromacs.command", shlex.join(gmx_command() or ()))
    job = new_job(
        workspace,
        "gromacs.run",
        inputs={"configuration": DATA / "ar.gro", "topology": DATA / "ar.top", "parameters": DATA / "em.mdp"},
        install=True,
    )
    with TaskManager(workspace, heartbeat_interval=0.01) as manager:
        manager.run_until_idle(timeout=600.0)
    [record] = job_records(workspace, states=("succeeded", "failed"))
    assert (record.job_id, record.state) == (job.job_id, "succeeded"), record.failure
    assert record.workdir is not None
    result = parse_mdrun_log(record.workdir / "run.log")
    assert result.potential_energy_kj_mol == pytest.approx(-13.4827, abs=1e-3)
    assert (result.converged, result.completed) == (True, True)

    register_workspace("gromacs", str(workspace.root))
    database = tmp_path / "results.sqlite"
    arguments = [
        "collect",
        "--workspace",
        "gromacs",
        "--into",
        str(database),
        "--id-base",
        "httk.test",
        "--no-id-ledger",
    ]
    assert command(arguments, CLIContext("httk", tmp_path)) == 0
    report = json.loads(capsys.readouterr().out.splitlines()[0])
    assert report["run_only"] is True and report["stored"]["run"]

    with store.Backend.sqlite(database) as backend:
        searcher = store.SqlStore(backend).searcher()
        runs = list(searcher.results(run=searcher.variable(Run)))
        searcher = store.SqlStore(backend).searcher()
        records = list(searcher.results(record=searcher.variable(DataRecord)))
    assert len(runs) == 1 and records == []
    # The package declares no declaration_uri, like qe.scf.
    assert runs[0].run.workflow_declaration_uri is None
