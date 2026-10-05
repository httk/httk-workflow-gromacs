"""Supervised ``grompp`` + ``mdrun`` execution and its classified run report."""

import dataclasses
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from httk.workflow.codes import Diagnostic, ProcessReport, ProcessSupervisor, launch_command, write_json_atomic

from .diagnostics import diagnose_gromacs
from .outputs import GromacsResult, _parse, _read, parse_fatal_errors

__all__ = ["GromacsRunReport", "run_gromacs"]


@dataclass(frozen=True)
class GromacsRunReport:
    """Classified result of one supervised GROMACS run: ``grompp``, then ``mdrun``.

    The classification is one of ``completed``, ``crashed`` (a
    ``gromacs.fatal`` diagnostic, including every ``grompp`` failure),
    ``nonconverged`` (an energy minimization that did not converge),
    ``process_failure`` (a nonzero exit or an incomplete log) and ``timeout``.

    :param grompp: The supervised ``grompp`` process result.
    :param mdrun: The supervised ``mdrun`` process result, or ``None`` when ``grompp`` failed.
    :param classification: The final run classification.
    :param diagnostics: The diagnostics of the finished run.
    :param result: What the ``mdrun`` log says (empty when ``mdrun`` did not run).
    """

    grompp: ProcessReport
    mdrun: ProcessReport | None
    classification: str
    diagnostics: tuple[Diagnostic, ...]
    result: GromacsResult

    @property
    def ok(self) -> bool:
        """Whether the run completed cleanly (and a minimization converged)."""
        return self.classification == "completed"

    def as_mapping(self) -> dict[str, object]:
        """Serialize the report for JSON storage.

        :return: The JSON-compatible report mapping.
        """
        result = {field.name: getattr(self.result, field.name) for field in dataclasses.fields(self.result)}
        return {
            "format": "httk-gromacs-run-report",
            "format_version": 1,
            "grompp": self.grompp.as_mapping(),
            "mdrun": None if self.mdrun is None else self.mdrun.as_mapping(),
            "classification": self.classification,
            "diagnostics": [item.as_mapping() for item in self.diagnostics],
            "result": {
                **result,
                "energies": dict(self.result.energies),
                "average_energies": None
                if self.result.average_energies is None
                else dict(self.result.average_energies),
                "errors": list(self.result.errors),
            },
        }

    def write(self, path: str | os.PathLike[str]) -> Path:
        """Write the report as JSON.

        :param path: Write the report to this path.
        :return: The report path.
        """
        destination = Path(path)
        write_json_atomic(destination, self.as_mapping())
        return destination


def run_gromacs(
    *,
    directory: str | os.PathLike[str] = ".",
    grompp_argv: Sequence[str],
    mdrun_argv: Sequence[str],
    deffnm: str = "run",
    timeout: float | None = None,
    launch: bool | None = None,
    termination_grace: float = 10.0,
    report_path: str | os.PathLike[str] = "gromacs-run-report.json",
) -> GromacsRunReport:
    """Run ``grompp`` and then ``mdrun`` under supervision and write a classified report.

    Both argument vectors name the program, e.g.
    ``["gmx", "grompp", "-f", "run.mdp", "-c", "conf.gro", "-p", "topol.top",
    "-o", "run.tpr"]`` and ``["gmx", "mdrun", "-deffnm", "run", "-nt", "1"]``;
    *deffnm* names the log ``mdrun`` writes, ``DEFFNM.log``. The standard output
    and error of each step are saved as ``grompp.out``/``grompp.err`` and
    ``mdrun.out``/``mdrun.err``, replacing those of an earlier run. ``mdrun``
    runs only when ``grompp`` succeeded; a failed ``grompp`` is ``crashed``
    with its error message as the diagnostic. *timeout* applies to each step
    separately.

    The attempt's launch prefix (the parallel start, ``HTTK_WORKFLOW_LAUNCH``) is
    prepended to the ``mdrun`` command only, by default; ``grompp`` always runs
    serially as given. ``launch=False`` runs ``mdrun`` as given too. A command that
    already starts with a launcher such as ``srun`` or ``mpirun`` is refused with
    :class:`ValueError` when a prefix applies (to ``grompp`` whenever a prefix is set).

    :param directory: Run both steps in this directory.
    :param grompp_argv: The ``grompp`` command argument vector.
    :param mdrun_argv: The ``mdrun`` command argument vector.
    :param deffnm: The ``mdrun -deffnm`` name the log is read from.
    :param timeout: Stop a step after this many seconds when set.
    :param launch: Prepend the attempt's launch prefix to ``mdrun`` when true, the default
        (``None``); ``False`` runs it as given.
    :param termination_grace: Allow this many seconds for graceful termination.
    :param report_path: Write the report at this directory-relative path.
    :return: The classified run report.
    """

    launch_command(grompp_argv)  # only the check: grompp is never prefixed, but must not be a launcher either
    mdrun_command = launch_command(mdrun_argv, launch=launch is not False)
    root = Path(directory).resolve()
    supervisor = ProcessSupervisor()

    def supervised(argv: Sequence[str], step: str) -> ProcessReport:
        # ponytail: no live monitor or remedy ladder; add them when a real campaign needs them.
        return supervisor.run(
            argv,
            timeout=timeout,
            cwd=root,
            termination_grace=termination_grace,
            stdout_path=root / f"{step}.out",
            stderr_path=root / f"{step}.err",
        )

    grompp = supervised(grompp_argv, "grompp")
    mdrun: ProcessReport | None = None
    if grompp.timed_out:
        classification, diagnostics = "timeout", grompp.diagnostics
    elif grompp.returncode:
        errors = parse_fatal_errors(_read(root / "grompp.err") + "\n" + _read(root / "grompp.out"))
        summary = errors[0] if errors else f"gmx grompp exited with status {grompp.returncode}"
        fatal = Diagnostic("gromacs.fatal", "fatal", summary, "grompp.err", "\n".join(errors) or None)
        classification, diagnostics = "crashed", (*grompp.diagnostics, fatal)
    else:
        mdrun = supervised(mdrun_command, "mdrun")
        diagnostics = (*grompp.diagnostics, *mdrun.diagnostics, *diagnose_gromacs(root, deffnm=deffnm))
        codes = {item.code for item in diagnostics}
        if mdrun.timed_out:
            classification = "timeout"
        elif "gromacs.fatal" in codes:
            classification = "crashed"
        elif mdrun.returncode or "gromacs.incomplete" in codes:
            classification = "process_failure"
        elif "gromacs.em_not_converged" in codes:
            classification = "nonconverged"
        elif any(item.severity in {"error", "fatal"} for item in diagnostics):
            classification = "process_failure"
        else:
            classification = "completed"
    result = _parse(_read(root / f"{deffnm}.log") if mdrun is not None else "")
    report = GromacsRunReport(grompp, mdrun, classification, diagnostics, result)
    report.write(root / report_path)
    return report
