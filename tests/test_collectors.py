"""The ``gromacs.calculation`` collector recognizes and collects free-standing runs via ``collect_tree``."""

import bz2
import shutil
from pathlib import Path

import pytest
from httk.workflow import claims, collect_tree
from httk.workflow.calculations import content_digest

from conftest import DATA
from httk.codes.gromacs import KJ_MOL_TO_EV
from httk.codes.gromacs.collect import find_outputs

ENERGY = -4.41489 * KJ_MOL_TO_EV


def _run(directory: Path, log: str = "md.log", stem: str = "run") -> Path:
    directory.mkdir(parents=True)
    shutil.copy(DATA / log, directory / f"{stem}.log")
    (directory / f"{stem}.tpr").write_bytes(b"synthetic tpr")
    return directory


def test_an_md_run_is_collected(tmp_path: Path) -> None:
    directory = _run(tmp_path / "argon")
    (item,) = collect_tree(tmp_path)
    assert item.missing_collector is None
    # The command line holds no physics option, so the identity is the plain digest.
    assert item.run.source_id == f"gromacs.calculation:{content_digest(directory, ['run.tpr'])}"
    assert item.outputs["average_total_energy"].value == pytest.approx(ENERGY)  # type: ignore[attr-defined]


def test_the_mdp_identifies_a_run_without_tpr(tmp_path: Path) -> None:
    directory = _run(tmp_path / "argon")
    (directory / "run.tpr").unlink()
    (directory / "run.mdp").write_text("integrator = md\n", encoding="utf-8")
    (item,) = collect_tree(tmp_path)
    assert item.run.source_id == f"gromacs.calculation:{content_digest(directory, ['run.mdp'])}"


def test_an_energy_minimisation_is_claimed_and_degraded(tmp_path: Path) -> None:
    _run(tmp_path / "argon", "em.log")
    (outcome,) = claims(tmp_path)
    assert outcome.kind == "claimed" and outcome.collector == "gromacs.calculation"
    (item,) = collect_tree(tmp_path)
    assert item.missing_collector is not None and "has no averages section" in item.missing_collector


def test_a_log_without_the_banner_is_no_candidate(tmp_path: Path) -> None:
    (tmp_path / "other.log").write_text("some other program\n" * 5, encoding="utf-8")
    assert list(claims(tmp_path)) == []
    assert find_outputs(tmp_path) == ()


def test_several_logs_are_unclaimed(tmp_path: Path) -> None:
    directory = _run(tmp_path / "argon")
    shutil.copy(DATA / "md.log", directory / "other.log")
    (outcome,) = claims(tmp_path)
    assert outcome.kind == "unclaimed"
    assert outcome.reason == "several GROMACS mdrun logs: other.log, run.log"
    assert list(collect_tree(tmp_path)) == []


def test_a_missing_input_is_unclaimed(tmp_path: Path) -> None:
    directory = _run(tmp_path / "argon")
    (directory / "run.tpr").unlink()
    (outcome,) = claims(tmp_path)
    assert (outcome.kind, outcome.reason) == ("unclaimed", "no run.tpr or run.mdp beside run.log")


def test_a_compressed_log_is_collected(tmp_path: Path) -> None:
    directory = _run(tmp_path / "argon")
    (directory / "run.log.bz2").write_bytes(bz2.compress((directory / "run.log").read_bytes()))
    (directory / "run.log").unlink()
    (item,) = collect_tree(tmp_path)
    assert item.missing_collector is None
    assert item.outputs["average_total_energy"].value == pytest.approx(ENERGY)  # type: ignore[attr-defined]


def _identity(tmp_path: Path, name: str, command: str) -> str | None:
    _run(tmp_path / name)
    log = tmp_path / name / "run.log"
    log.write_text(log.read_text().replace("gmx mdrun -deffnm md -nt 1", command))
    (item,) = collect_tree(tmp_path / name)
    return item.run.source_id


def test_the_identity_ignores_threads_and_paths(tmp_path: Path) -> None:
    one = _identity(tmp_path, "a", "gmx mdrun -deffnm md -nt 1 -s /home/x/run.tpr")
    other = _identity(tmp_path, "b", "gmx_mpi mdrun -ntomp 8 -pin on -s /scratch/y/run.tpr -maxh 1")
    assert one == other


def test_nsteps_and_continuation_change_the_identity(tmp_path: Path) -> None:
    plain = _identity(tmp_path, "a", "gmx mdrun -deffnm md")
    steps = _identity(tmp_path, "b", "gmx mdrun -deffnm md -nsteps 10")
    cont = _identity(tmp_path, "c", "gmx mdrun -deffnm md -cpi md.cpt")
    assert len({plain, steps, cont}) == 3


def test_a_truncated_appended_part_is_degraded(tmp_path: Path) -> None:
    directory = _run(tmp_path / "argon")
    log = directory / "run.log"
    text = log.read_text()
    log.write_text(text + text[: text.index("Started mdrun")])
    (item,) = collect_tree(tmp_path)
    assert item.missing_collector is not None and "has no averages section" in item.missing_collector


def test_a_finished_appended_part_gives_its_own_averages(tmp_path: Path) -> None:
    directory = _run(tmp_path / "argon")
    log = directory / "run.log"
    text = log.read_text()
    log.write_text(text + text.replace("-4.41489e+00", "-3.00000e+00"))
    (item,) = collect_tree(tmp_path)
    assert item.outputs["average_total_energy"].value == pytest.approx(-3.0 * KJ_MOL_TO_EV)  # type: ignore[attr-defined]


def test_a_log_without_a_command_line_keeps_the_plain_identity(tmp_path: Path) -> None:
    directory = _run(tmp_path / "a")
    log = directory / "run.log"
    log.write_text(log.read_text().replace("Command line:", "Cmd:"))
    (item,) = collect_tree(tmp_path)
    assert item.run.source_id == f"gromacs.calculation:{content_digest(directory, ['run.tpr'])}"
