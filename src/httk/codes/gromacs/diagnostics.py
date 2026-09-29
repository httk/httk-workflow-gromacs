"""Classify a finished GROMACS run into stable diagnostics."""

import os
from pathlib import Path

from httk.workflow.codes import Diagnostic

from .outputs import _parse, _read, parse_fatal_errors

__all__ = ["diagnose_gromacs"]

#: The standard error files of the two steps, as :func:`~httk.codes.gromacs.run_gromacs` saves them.
_STDERR_FILES = ("grompp.err", "mdrun.err")


def diagnose_gromacs(directory: str | os.PathLike[str] = ".", *, deffnm: str = "run") -> tuple[Diagnostic, ...]:
    """Diagnose a GROMACS run from its ``mdrun`` log and saved standard error.

    The codes are stable: ``gromacs.fatal`` (fatal; ``grompp`` or ``mdrun``
    stopped with a ``Fatal error``, the summary is its message),
    ``gromacs.em_not_converged`` (error; an energy minimization did not reach
    its force tolerance, including one that stopped at machine precision), and ``gromacs.incomplete`` (error; the log has no
    ``Finished mdrun`` and there is no error message, e.g. a killed process). A
    completed run has none. A missing log is diagnosed like an empty one.

    :param directory: Read the run files from this directory.
    :param deffnm: The ``mdrun -deffnm`` name: the log is ``DEFFNM.log``; the
        ``grompp.err`` and ``mdrun.err`` files beside it are read too.
    :return: The diagnostics, empty for a clean run.
    """

    root = Path(directory)
    log = f"{deffnm}.log"
    text = _read(root / log)
    result = _parse(text)
    diagnostics: list[Diagnostic] = []
    for source in (log, *_STDERR_FILES):
        errors = result.errors if source == log else parse_fatal_errors(_read(root / source))
        if errors:
            diagnostics.append(Diagnostic("gromacs.fatal", "fatal", errors[0], source, "\n".join(errors)))
            break
    else:
        if not result.completed:
            diagnostics.append(Diagnostic("gromacs.incomplete", "error", f"{log} has no Finished mdrun line", log))
    if result.converged is False:
        diagnostics.append(
            Diagnostic(
                "gromacs.em_not_converged",
                "error",
                f"energy minimization stopped at machine precision in {result.steps} steps, "
                "short of its force tolerance"
                if "converged to machine precision" in text
                else f"energy minimization did not converge to its force tolerance in {result.steps} steps",
                log,
            )
        )
    return tuple(diagnostics)
