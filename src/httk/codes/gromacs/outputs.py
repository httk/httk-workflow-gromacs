"""Parse the text output of GROMACS: the ``mdrun`` log and ``Fatal error`` blocks.

Pure stdlib parsing: nothing here runs a program or imports *httk* code, so a
result can be read anywhere the output file is.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

__all__ = ["KJ_MOL_TO_EV", "GromacsResult", "parse_fatal_errors", "parse_mdrun_log"]

#: One kJ/mol in electronvolts per particle (CODATA 2018), for GROMACS's energy unit.
KJ_MOL_TO_EV: float = 0.010364269656262175

# GROMACS prints each energies table as rows of names and values in 15-character columns.
_COLUMN = 15
_ENERGIES_HEADER = "Energies (kJ/mol)"
# The run-averages section repeats the table; only the instantaneous tables before it count.
_AVERAGES = "<====  A V E R A G E S  ====>"
# "converged to machine precision" stopped short of the requested Fmax: not converged.
_EM_RESULT = re.compile(
    r"^\S.*? (converged|did not converge) to (Fmax < \S+|machine precision) in (\d+) steps", re.MULTILINE
)
_EM_POTENTIAL = re.compile(r"^Potential Energy\s+=\s+(\S+)", re.MULTILINE)
_STEP_ROW = re.compile(r"^\s+Step\s+Time\s*\n\s+(\d+)\s", re.MULTILINE)
_FATAL = re.compile(r"^Fatal error:[ \t]*\n(.*?)(?:\n[ \t]*\n|\n-{20,}|\Z)", re.MULTILINE | re.DOTALL)
# grompp reports each input problem as "ERROR n [file F, line L]:" plus an indented message.
_INPUT_ERROR = re.compile(r"^ERROR \d+(?: \[file ([^\]]*)\])?:[ \t]*\n(.*?)(?:\n[ \t]*\n|\Z)", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class GromacsResult:
    """What one ``mdrun`` log says about its run.

    :param potential_energy_kj_mol: The final potential energy in kJ/mol: the
        ``Potential Energy`` line of an energy minimization, else the
        ``Potential`` term of the last energies table, or ``None``.
    :param energies: The last instantaneous ``Energies (kJ/mol)`` table, term name to value
        (``Pressure (bar)`` and ``Temperature`` keep their own units).
    :param converged: Whether an energy minimization converged to its force
        tolerance (stopping at machine precision short of it is ``False``);
        ``None`` for dynamics or when the log reports no result.
    :param steps: The minimization step count GROMACS reports, else the last logged step, or ``None``.
    :param completed: Whether the log reached ``Finished mdrun``.
    :param errors: The messages of ``Fatal error`` blocks in the log.
    """

    potential_energy_kj_mol: float | None
    energies: Mapping[str, float]
    converged: bool | None
    steps: int | None
    completed: bool
    errors: tuple[str, ...]

    @property
    def potential_energy_ev(self) -> float | None:
        """The final potential energy in eV, or ``None``."""
        return None if self.potential_energy_kj_mol is None else self.potential_energy_kj_mol * KJ_MOL_TO_EV


def parse_mdrun_log(path: str | os.PathLike[str]) -> GromacsResult:
    """Parse one ``mdrun`` log file (``DEFFNM.log``).

    :param path: Read the log at this path.
    :return: The parsed result.
    :raises FileNotFoundError: If the log does not exist.
    """

    return _parse(Path(path).read_text(encoding="utf-8", errors="replace"))


def parse_fatal_errors(text: str) -> tuple[str, ...]:
    """Extract the error messages of GROMACS output, such as ``grompp`` or ``mdrun`` standard error.

    ``grompp``'s numbered input errors (``ERROR 1 [file topol.top, line 23]:``)
    come first, as ``"topol.top, line 23: message"``, then the messages of the
    ``Fatal error:`` blocks, each once, with lines joined by spaces.

    :param text: The GROMACS output text.
    :return: The error messages in order of appearance.
    """

    errors: list[str] = []
    for location, message in _INPUT_ERROR.findall(text):
        joined = " ".join(message.split()).removeprefix("ERROR: ")
        errors.append(f"{location}: {joined}" if location else joined)
    errors.extend(" ".join(message.split()) for message in _FATAL.findall(text))
    return tuple(dict.fromkeys(entry for entry in errors if entry))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _last_energies(text: str) -> dict[str, float]:
    lines = text.split(_AVERAGES, 1)[0].splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == _ENERGIES_HEADER]
    energies: dict[str, float] = {}
    if not starts:
        return energies
    rows = lines[starts[-1] + 1 :]
    # Name and value rows alternate until the blank line that ends the table; the
    # values are whitespace separated, the names fixed width (a name holds spaces).
    for names, values in zip(rows[::2], rows[1::2], strict=False):
        if not names.strip() or not values.strip():
            break
        numbers = values.split()
        width = max(len(names), _COLUMN * len(numbers))
        padded = names.rjust(width)
        labels = [padded[i : i + _COLUMN].strip() for i in range(width - _COLUMN * len(numbers), width, _COLUMN)]
        try:
            parsed = [float(number) for number in numbers]
        except ValueError:
            break
        energies.update(zip(labels, parsed, strict=True))
    return energies


def _parse(text: str) -> GromacsResult:
    energies = _last_energies(text)
    em_results = _EM_RESULT.findall(text)
    em_potentials = _EM_POTENTIAL.findall(text)
    steps = _STEP_ROW.findall(text)
    if em_potentials:
        potential: float | None = float(em_potentials[-1])
    else:
        potential = energies.get("Potential")
    return GromacsResult(
        potential_energy_kj_mol=potential,
        energies=MappingProxyType(energies),
        converged=em_results[-1][0] == "converged" and em_results[-1][1] != "machine precision" if em_results else None,
        steps=int(em_results[-1][2]) if em_results else int(steps[-1]) if steps else None,
        completed="Finished mdrun" in text,
        errors=parse_fatal_errors(text),
    )
