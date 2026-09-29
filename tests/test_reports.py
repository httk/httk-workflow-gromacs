"""``run_gromacs`` classifies a supervised run and writes its report.

Stand-in ``grompp`` and ``mdrun`` commands replay captured output, so the
classification is exercised without a real ``gmx``.
"""

import json
import sys
from pathlib import Path

import pytest

from conftest import DATA
from httk.codes.gromacs import run_gromacs

# grompp: print a captured standard error (or nothing for "-") and exit with a code.
_GROMPP = "import sys; sys.argv[1] != '-' and sys.stderr.write(open(sys.argv[1]).read()); sys.exit(int(sys.argv[2]))"
# mdrun: copy a captured log to run.log and exit with a code.
_MDRUN = "import shutil, sys; shutil.copy(sys.argv[1], 'run.log'); sys.exit(int(sys.argv[2]))"


def _grompp(stderr: str | None = None, code: int = 0) -> list[str]:
    return [sys.executable, "-c", _GROMPP, str(DATA / stderr) if stderr else "-", str(code)]


def _mdrun(log: str, code: int = 0) -> list[str]:
    return [sys.executable, "-c", _MDRUN, str(DATA / log), str(code)]


@pytest.mark.parametrize(
    ("grompp", "mdrun", "classification"),
    [
        (_grompp(), _mdrun("em.log"), "completed"),
        (_grompp(), _mdrun("md.log"), "completed"),
        (_grompp(), _mdrun("em_noconv.log"), "nonconverged"),
        (_grompp(), _mdrun("em_machine_precision.log"), "nonconverged"),
        (_grompp(), _mdrun("em.log", 3), "process_failure"),
        (_grompp("grompp_fatal.err", 1), _mdrun("em.log"), "crashed"),
    ],
)
def test_the_run_is_classified_and_reported(
    tmp_path: Path, grompp: list[str], mdrun: list[str], classification: str
) -> None:
    report = run_gromacs(directory=tmp_path, grompp_argv=grompp, mdrun_argv=mdrun)
    assert report.classification == classification
    assert report.ok == (classification == "completed")
    saved = json.loads((tmp_path / "gromacs-run-report.json").read_text(encoding="utf-8"))
    assert saved["format"] == "httk-gromacs-run-report" and saved["classification"] == classification
    assert (tmp_path / "grompp.err").is_file()
    if classification == "completed":
        assert report.diagnostics == ()
        assert saved["result"]["energies"]["Potential"] == report.result.energies["Potential"]


def test_a_grompp_failure_skips_mdrun_and_reports_the_fatal_error(tmp_path: Path) -> None:
    report = run_gromacs(directory=tmp_path, grompp_argv=_grompp("grompp_fatal.err", 1), mdrun_argv=_mdrun("em.log"))
    assert report.mdrun is None and not (tmp_path / "run.log").exists()
    (diagnostic,) = report.diagnostics
    assert diagnostic.code == "gromacs.fatal" and "cut-off length" in diagnostic.summary
    assert report.result.potential_energy_kj_mol is None
    # A grompp that fails without an error message is still crashed.
    silent = run_gromacs(directory=tmp_path, grompp_argv=_grompp(None, 4), mdrun_argv=_mdrun("em.log"))
    assert silent.classification == "crashed"
    assert silent.diagnostics[-1].summary == "gmx grompp exited with status 4"


def test_the_completed_report_carries_the_parsed_result(tmp_path: Path) -> None:
    report = run_gromacs(directory=tmp_path, grompp_argv=_grompp(), mdrun_argv=_mdrun("em.log"), deffnm="run")
    assert report.mdrun is not None and report.mdrun.returncode == 0
    assert (report.result.potential_energy_kj_mol, report.result.converged) == (-13.48265, True)
