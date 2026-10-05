"""The attempt's launch prefix reaches mdrun, and only mdrun."""

import sys
from pathlib import Path

import pytest

from httk.codes.gromacs import GromacsRunReport, run_gromacs

PROGRAM = [sys.executable, "-c", "pass"]


def _run(tmp_path: Path, **keywords: object) -> GromacsRunReport:
    # A grompp that exits 0 lets mdrun run; the report then holds both argvs.
    return run_gromacs(directory=tmp_path, grompp_argv=PROGRAM, mdrun_argv=PROGRAM, **keywords)  # type: ignore[arg-type]


def test_the_prefix_is_prepended_to_mdrun_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTK_WORKFLOW_LAUNCH", "env 'A=b c'")
    report = _run(tmp_path)
    assert report.grompp.argv[0] == sys.executable
    assert report.mdrun is not None and report.mdrun.argv[:3] == ("env", "A=b c", sys.executable)


def test_launch_false_runs_mdrun_as_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTK_WORKFLOW_LAUNCH", "env A=b")
    report = _run(tmp_path, launch=False)
    assert report.mdrun is not None and report.mdrun.argv[0] == sys.executable


def test_no_prefix_changes_nothing(tmp_path: Path) -> None:
    report = _run(tmp_path)
    assert report.mdrun is not None and report.mdrun.argv[0] == sys.executable


def test_a_launcher_is_refused_when_a_prefix_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTK_WORKFLOW_LAUNCH", "env A=b")
    with pytest.raises(ValueError, match="manager.launch_template"):
        run_gromacs(directory=tmp_path, grompp_argv=PROGRAM, mdrun_argv=["srun", "gmx", "mdrun"])


def test_a_launcher_as_grompp_is_refused_when_a_prefix_is_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTK_WORKFLOW_LAUNCH", "env A=b")
    with pytest.raises(ValueError, match="manager.launch_template"):
        run_gromacs(directory=tmp_path, grompp_argv=["mpirun", "gmx", "grompp"], mdrun_argv=PROGRAM, launch=False)
