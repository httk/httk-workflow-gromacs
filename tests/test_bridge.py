"""The ``gromacs-*`` bridge commands and the Bash API that forwards to them.

Code verbs need no attempt, so they run straight through the shell bridge.
Sibling code packages installed in the same environment may report on standard
error, so it is not asserted empty.
"""

import json
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest

from conftest import DATA


def _environment() -> dict[str, str]:
    environment = {name: value for name, value in os.environ.items() if not name.startswith("HTTK_WORKFLOW_")}
    environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    return environment


def _bridge(cwd: Path, *arguments: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        [sys.executable, "-m", "httk.workflow._shell_bridge", *arguments],
        cwd=cwd,
        env=_environment(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_energy_terms_units_convergence_and_absences(tmp_path: Path) -> None:
    energy = _bridge(tmp_path, "gromacs-energy", "--log", str(DATA / "em.log"))
    assert (energy.returncode, energy.stdout) == (0, "-13.48265\n")
    in_ev = _bridge(tmp_path, "gromacs-energy", "--log", str(DATA / "em.log"), "--unit", "ev")
    assert float(in_ev.stdout) == pytest.approx(-13.48265 * 0.010364269656262175)
    kinetic = _bridge(tmp_path, "gromacs-energy", "--log", str(DATA / "md.log"), "--term", "Kinetic En.")
    assert (kinetic.returncode, kinetic.stdout) == (0, "8.52098\n")
    missing_term = _bridge(tmp_path, "gromacs-energy", "--log", str(DATA / "em.log"), "--term", "Kinetic En.")
    assert (missing_term.returncode, missing_term.stdout) == (1, "")
    assert _bridge(tmp_path, "gromacs-converged", "--log", str(DATA / "em.log")).returncode == 0
    for log in ("em_noconv.log", "md.log"):
        absent = _bridge(tmp_path, "gromacs-converged", "--log", str(DATA / log))
        assert (absent.returncode, absent.stdout) == (1, "")
    refused = _bridge(tmp_path, "gromacs-energy", "--log", str(tmp_path / "missing.log"))
    assert refused.returncode == 2


def test_diagnose_prints_codes_and_json(tmp_path: Path) -> None:
    clean = _bridge(tmp_path, "gromacs-diagnose", "--log", str(DATA / "em.log"))
    assert (clean.returncode, clean.stdout) == (0, "")
    shutil.copy(DATA / "grompp_fatal.err", tmp_path / "grompp.err")
    fatal = _bridge(tmp_path, "gromacs-diagnose", "--json")
    assert fatal.returncode == 20
    assert [item["code"] for item in json.loads(fatal.stdout)] == ["gromacs.fatal"]
    noconv = _bridge(tmp_path, "gromacs-diagnose", "--log", str(DATA / "em_noconv.log"))
    assert (noconv.returncode, noconv.stdout.split("\t")[0]) == (20, "gromacs.em_not_converged")


def test_run_with_a_stand_in_gmx(tmp_path: Path) -> None:
    # A stand-in gmx: grompp succeeds silently, mdrun writes the captured unconverged log as DEFFNM.log.
    stand_in = tmp_path / "gmx.py"
    stand_in.write_text(
        "import shutil, sys\n"
        "if sys.argv[1] == 'mdrun':\n"
        f"    shutil.copy({str(DATA / 'em_noconv.log')!r}, sys.argv[sys.argv.index('-deffnm') + 1] + '.log')\n",
        encoding="utf-8",
    )
    ran = _bridge(
        tmp_path, "gromacs-run", "--deffnm", "em", "--mdrun-options=-nt 1", "--", sys.executable, str(stand_in)
    )
    assert (ran.returncode, ran.stdout) == (21, "gromacs-run-report.json\n"), ran.stderr
    report = json.loads((tmp_path / "gromacs-run-report.json").read_text(encoding="utf-8"))
    assert report["classification"] == "nonconverged"
    assert report["grompp"]["argv"][2:] == [
        "grompp",
        "-f",
        "em.mdp",
        "-c",
        "conf.gro",
        "-p",
        "topol.top",
        "-o",
        "em.tpr",
    ]
    assert report["mdrun"]["argv"][2:] == ["mdrun", "-deffnm", "em", "-nt", "1"]
    assert _bridge(tmp_path, "gromacs-run").returncode == 2


def test_the_bash_api_forwards_to_the_bridge(tmp_path: Path) -> None:
    workflow_api = files("httk.workflow").joinpath("languages", "bash", "httk-workflow.sh")
    gromacs_api = files("httk.codes.gromacs").joinpath("httk-gromacs.sh")
    script = (
        f'source "{workflow_api}"; source "{gromacs_api}"; '
        f'[ "$HTTK_GROMACS_BASH_API_VERSION" = 1 ] && httk_gromacs_energy --log "{DATA / "md.log"}" --term Temperature'
    )
    environment = _environment()
    environment["HTTK_WORKFLOW_PYTHON"] = sys.executable
    result = subprocess.run(
        ["bash", "-c", script], cwd=tmp_path, env=environment, text=True, capture_output=True, check=False
    )
    assert (result.returncode, result.stdout) == (0, "97.6037\n"), result.stderr
    unguarded = subprocess.run(
        ["bash", "-c", f'source "{gromacs_api}"; httk_gromacs_energy'], text=True, capture_output=True, check=False
    )
    assert unguarded.returncode == 2 and "source HTTK_WORKFLOW_BASH_API" in unguarded.stderr


def test_no_launch_runs_mdrun_as_given(tmp_path: Path) -> None:
    # _bridge strips HTTK_WORKFLOW_*; call the bridge directly with a launch prefix set.
    environment = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
        "HTTK_WORKFLOW_LAUNCH": "env A=b",
    }
    command = [sys.executable, "-m", "httk.workflow._shell_bridge", "gromacs-run"]
    program = ["--", sys.executable, "-c", "pass"]

    def mdrun_argv(*flags: str) -> list[str]:
        result = subprocess.run(
            [*command, *flags, *program], cwd=tmp_path, env=environment, text=True, capture_output=True, check=False
        )
        assert result.returncode == 22
        return json.loads((tmp_path / "gromacs-run-report.json").read_text(encoding="utf-8"))["mdrun"]["argv"]

    assert mdrun_argv("--no-launch")[0] == sys.executable
    assert mdrun_argv()[:2] == ["env", "A=b"]
