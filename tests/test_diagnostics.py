"""``diagnose_gromacs`` maps finished runs to the stable ``gromacs.*`` codes."""

import shutil
from pathlib import Path

from conftest import DATA
from httk.codes.gromacs import diagnose_gromacs


def _codes(directory: Path, deffnm: str = "run") -> list[tuple[str, str]]:
    return [(item.code, item.severity) for item in diagnose_gromacs(directory, deffnm=deffnm)]


def test_completed_runs_have_no_diagnostics() -> None:
    assert diagnose_gromacs(DATA, deffnm="em") == ()
    assert diagnose_gromacs(DATA, deffnm="md") == ()


def test_an_unconverged_minimization_is_an_error() -> None:
    assert _codes(DATA, "em_noconv") == [("gromacs.em_not_converged", "error")]


def test_a_minimization_stopped_at_machine_precision_is_not_converged() -> None:
    (diagnostic,) = diagnose_gromacs(DATA, deffnm="em_machine_precision")
    assert (diagnostic.code, diagnostic.severity) == ("gromacs.em_not_converged", "error")
    assert "machine precision in 94 steps" in diagnostic.summary


def test_a_grompp_fatal_error_is_fatal_and_names_the_input_error(tmp_path: Path) -> None:
    shutil.copy(DATA / "grompp_fatal.err", tmp_path / "grompp.err")
    (diagnostic,) = diagnose_gromacs(tmp_path)
    assert (diagnostic.code, diagnostic.severity, diagnostic.source) == ("gromacs.fatal", "fatal", "grompp.err")
    assert diagnostic.summary.startswith("ar.top, line 23: The cut-off length is longer")
    assert diagnostic.evidence is not None and "There was 1 error" in diagnostic.evidence


def test_a_truncated_or_missing_log_is_incomplete(tmp_path: Path) -> None:
    text = (DATA / "md.log").read_text(encoding="utf-8")
    (tmp_path / "run.log").write_text(text[: len(text) // 2], encoding="utf-8")
    assert _codes(tmp_path) == [("gromacs.incomplete", "error")]
    assert _codes(tmp_path, "absent") == [("gromacs.incomplete", "error")]
