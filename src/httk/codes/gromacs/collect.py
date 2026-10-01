"""Building blocks for the collect hooks of GROMACS workflows."""

from pathlib import Path

from httk.core import DataRecord
from httk.core.datastream.compression import open_compressed, split_compression_suffix

from .outputs import parse_mdrun_log

__all__ = ["find_outputs", "read_average_total_energy", "read_command_line"]

_AVERAGE_TOTAL_ENERGY_DEFINITION = "https://schemas.httk.org/defs/v0.1/properties/core/average_total_energy"
_AVERAGE_TOTAL_ENERGY_NAME = "_httk_average_total_energy"
_BANNER = "GROMACS - gmx mdrun"
_HEAD_LINES = 100


def _has_banner(path: Path) -> bool:
    """Whether the ``gmx mdrun`` banner appears within the first lines of *path*."""

    try:
        with path.open("rb") as raw, open_compressed(raw, compression="extension", name=path.name) as stream:
            for number, line in enumerate(stream):
                if number >= _HEAD_LINES:
                    return False
                if _BANNER in line.decode("utf-8", "replace"):
                    return True
    except (OSError, EOFError):
        pass
    return False


def find_outputs(directory: Path) -> tuple[Path, ...]:
    """Find the ``mdrun`` log files of a directory, sorted by name.

    A ``*.log`` file (optionally compressed) counts as a log when the banner
    ``GROMACS - gmx mdrun`` appears within its first 100 lines; only that head is
    read, so other programs' logs are rejected cheaply.

    :param directory: The directory to look in.
    :return: The log files, sorted by name.
    """

    names = sorted(
        path
        for path in Path(directory).iterdir()
        if path.is_file() and split_compression_suffix(path.name)[0].lower().endswith(".log")
    )
    return tuple(path for path in names if _has_banner(path))


def read_command_line(path: Path) -> str | None:
    """Read the ``mdrun`` invocation a log records after its ``Command line:`` line.

    Only the first 100 lines are read.

    :param path: The ``mdrun`` log, optionally compressed.
    :return: The stripped invocation, or ``None`` when the head has no ``Command line:`` line.
    """

    try:
        with path.open("rb") as raw, open_compressed(raw, compression="extension", name=path.name) as stream:
            previous = False
            for number, line in enumerate(stream):
                if number >= _HEAD_LINES:
                    break
                text = line.decode("utf-8", "replace").strip()
                if previous:
                    return text or None
                previous = text == "Command line:"
    except (OSError, EOFError):
        pass
    return None


def read_average_total_energy(path: Path) -> DataRecord:
    """Read the run-average total energy, in eV, from one ``mdrun`` log.

    This is the ``Total Energy`` that GROMACS itself prints in the
    ``A V E R A G E S`` section of the log (the last one, for a multi-part run).

    :param path: The ``mdrun`` log, optionally compressed.
    :return: The energy as an ``average_total_energy`` property record.
    :raises ValueError: If the log has no averages section, or the run did not complete.
    """

    result = parse_mdrun_log(path)
    energy = result.average_total_energy_ev
    if energy is None or not result.completed:
        raise ValueError(f"{path.name} has no averages section (an energy minimisation or an unfinished run)")
    return DataRecord.from_value(_AVERAGE_TOTAL_ENERGY_DEFINITION, _AVERAGE_TOTAL_ENERGY_NAME, energy)
