#!/usr/bin/env python3
"""gromacs.run: one GROMACS run of a prepared system.

The single ``run`` step copies the ``configuration``, ``topology`` and
``parameters`` inputs (staged as ``files/conf.gro``, ``files/topol.top`` and
``files/run.mdp``) into the workdir, runs ``gmx grompp`` and ``gmx mdrun
-deffnm run`` under supervision, and fails with the first diagnostic code
(``gromacs.fatal``, ``gromacs.em_not_converged``, ...) when the run is not
clean.

Settings, resolved job parameter -> ``HTTK_*`` variable -> workspace setting:

* ``gromacs.command``: the command that starts GROMACS (default ``gmx``), e.g.
  ``gmx_mpi`` or ``mpirun -np 4 gmx_mpi``;
* ``gromacs.mdrun_options``: extra ``mdrun`` options (default ``-nt 1``, one
  thread; e.g. ``-nt 8`` or ``-ntomp 4``).
"""

import shlex
import shutil

from httk.workflow import Attempt, Runner

from httk.codes.gromacs import run_gromacs

run = Runner("gromacs.run")


@run.step(name="run")
def run_step(a: Attempt) -> None:
    """Stage the inputs and run grompp and mdrun, then succeed or fail with what was diagnosed."""

    for name in ("conf.gro", "topol.top", "run.mdp"):
        shutil.copyfile(a.payload / "files" / name, a.workdir / name)
    gmx = shlex.split(str(a.setting("gromacs.command", "gmx")))
    mdrun_options = shlex.split(str(a.setting("gromacs.mdrun_options", "-nt 1")))
    try:
        report = run_gromacs(
            directory=a.workdir,
            grompp_argv=[*gmx, "grompp", "-f", "run.mdp", "-c", "conf.gro", "-p", "topol.top", "-o", "run.tpr"],
            mdrun_argv=[*gmx, "mdrun", "-deffnm", "run", *mdrun_options],
        )
    except OSError as exception:
        a.fail("gromacs.failed", f"could not start GROMACS: {exception}")
        return
    if not report.ok:
        first = report.diagnostics[0] if report.diagnostics else None
        code = first.code if first else f"gromacs.{report.classification}"
        a.fail(code, first.summary if first else f"GROMACS {report.classification}")
        return
    a.state.merge({"potential_energy_kj_mol": report.result.potential_energy_kj_mol})
    a.succeed()


if __name__ == "__main__":
    raise SystemExit(run.main())
