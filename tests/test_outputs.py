"""``parse_mdrun_log`` and ``parse_fatal_errors`` read real captured GROMACS 2026.3 output."""

from pathlib import Path

import pytest

from conftest import DATA
from httk.codes.gromacs import KJ_MOL_TO_EV, parse_fatal_errors, parse_mdrun_log


def test_a_converged_energy_minimization() -> None:
    result = parse_mdrun_log(DATA / "em.log")
    # The full-precision "Potential Energy =" line wins over the 6-digit table value.
    assert result.potential_energy_kj_mol == -13.48265
    assert result.potential_energy_ev == pytest.approx(-13.48265 * KJ_MOL_TO_EV)
    assert dict(result.energies) == {
        "LJ (SR)": -13.4826,
        "Coulomb (SR)": 0.0,
        "Potential": -13.4826,
        "Pressure (bar)": -14.0785,
    }
    assert (result.converged, result.steps, result.completed, result.errors) == (True, 1, True, ())


def test_an_energy_minimization_that_did_not_converge() -> None:
    result = parse_mdrun_log(DATA / "em_noconv.log")
    assert result.potential_energy_kj_mol == -14.975987
    # The last of the three per-step tables.
    assert result.energies["Potential"] == -14.976 and result.energies["Pressure (bar)"] == -3.21834
    assert (result.converged, result.steps, result.completed) == (False, 3, True)


def test_a_minimization_stopped_at_machine_precision_did_not_converge() -> None:
    result = parse_mdrun_log(DATA / "em_machine_precision.log")
    assert (result.potential_energy_kj_mol, result.converged, result.steps, result.completed) == (
        -18.726562,
        False,
        94,
        True,
    )


def test_md_reads_the_last_multi_row_table_not_the_averages() -> None:
    result = parse_mdrun_log(DATA / "md.log")
    assert dict(result.energies) == {
        "LJ (SR)": -12.9971,
        "Coulomb (SR)": 0.0,
        "Potential": -12.9971,
        "Kinetic En.": 8.52098,
        "Total Energy": -4.4761,
        "Conserved En.": -3.86326,
        "Temperature": 97.6037,
        "Pressure (bar)": -6.40613,
    }
    assert (result.potential_energy_kj_mol, result.converged, result.steps, result.completed) == (
        -12.9971,
        None,
        50,
        True,
    )


def test_a_truncated_log_has_no_finish_and_no_energies(tmp_path: Path) -> None:
    text = (DATA / "md.log").read_text(encoding="utf-8")
    (tmp_path / "run.log").write_text(text[: text.index("Energies (kJ/mol)")], encoding="utf-8")
    result = parse_mdrun_log(tmp_path / "run.log")
    assert (result.potential_energy_kj_mol, dict(result.energies), result.completed) == (None, {}, False)
    with pytest.raises(FileNotFoundError):
        parse_mdrun_log(tmp_path / "absent.log")


def test_grompp_input_errors_come_before_the_fatal_error() -> None:
    errors = parse_fatal_errors((DATA / "grompp_fatal.err").read_text(encoding="utf-8"))
    assert errors == (
        (
            "ar.top, line 23: The cut-off length is longer than half the shortest box vector or longer than "
            "the smallest box diagonal element. Increase the box size or decrease rlist."
        ),
        "There was 1 error in input file(s)",
    )
    assert parse_fatal_errors((DATA / "em.log").read_text(encoding="utf-8")) == ()
