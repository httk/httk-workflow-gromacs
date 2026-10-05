"""The ``gromacs-*`` subcommands of the private native Bash command bridge.

``httk.workflow._shell_bridge`` mounts these beside its own subcommands through
the ``codes`` registry tier, so each function of ``httk-gromacs.sh`` is one
invocation of one command here. A legitimately absent answer returns the
bridge's uniform exit code ``1``; a refused call raises, which the bridge
reports as ``2``. ``gromacs-run`` has its own outcome codes, the same as
``vasp-run``: ``0`` completed, ``20`` crashed, ``21`` nonconverged, ``22``
process failure, ``124`` timeout; ``gromacs-diagnose`` exits ``20`` when it
found anything, like ``vasp-diagnose``.
"""

import argparse
import json
import shlex
from pathlib import Path

from httk.workflow.codes import BRIDGE_ABSENT

from .diagnostics import diagnose_gromacs
from .outputs import KJ_MOL_TO_EV, parse_mdrun_log
from .reports import run_gromacs

_RUN_EXIT = {"completed": 0, "crashed": 20, "nonconverged": 21, "process_failure": 22, "timeout": 124}


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Register the ``gromacs-*`` subcommands on the bridge's subparsers.

    :param commands: the bridge's subcommand collection.
    """

    run = commands.add_parser("gromacs-run")
    run.add_argument("--directory", default=".")
    run.add_argument("--deffnm", default="run")
    run.add_argument("--configuration", default="conf.gro")
    run.add_argument("--topology", default="topol.top")
    run.add_argument("--mdrun-options", default="")
    run.add_argument("--timeout", type=float)
    run.add_argument("--launch", action=argparse.BooleanOptionalAction, default=None)
    run.add_argument("argv", nargs=argparse.REMAINDER)
    energy = commands.add_parser("gromacs-energy")
    energy.add_argument("--log", default="run.log")
    energy.add_argument("--term")
    energy.add_argument("--unit", choices=("kj_mol", "ev"), default="kj_mol")
    converged = commands.add_parser("gromacs-converged")
    converged.add_argument("--log", default="run.log")
    diagnose = commands.add_parser("gromacs-diagnose")
    diagnose.add_argument("--log", default="run.log")
    diagnose.add_argument("--json", action="store_true")


def run_command(arguments: argparse.Namespace) -> int:
    """Run one parsed ``gromacs-*`` subcommand.

    :param arguments: the parsed bridge command line.
    :return: the subcommand's exit code.
    """

    command = arguments.command
    if command == "gromacs-run":
        gmx = arguments.argv[1:] if arguments.argv[:1] == ["--"] else arguments.argv
        if not gmx:
            raise ValueError("gromacs-run needs the gmx command after --")
        deffnm = arguments.deffnm
        grompp = ["grompp", "-f", f"{deffnm}.mdp", "-c", arguments.configuration, "-p", arguments.topology]
        report = run_gromacs(
            directory=arguments.directory,
            grompp_argv=[*gmx, *grompp, "-o", f"{deffnm}.tpr"],
            mdrun_argv=[*gmx, "mdrun", "-deffnm", deffnm, *shlex.split(arguments.mdrun_options)],
            deffnm=deffnm,
            timeout=arguments.timeout,
            launch=arguments.launch,
        )
        print(Path(arguments.directory, "gromacs-run-report.json"))
        return _RUN_EXIT[report.classification]
    log = Path(arguments.log)
    if command == "gromacs-diagnose":
        diagnostics = diagnose_gromacs(log.parent, deffnm=log.name.removesuffix(".log"))
        if arguments.json:
            print(json.dumps([item.as_mapping() for item in diagnostics], sort_keys=True))
        else:
            for item in diagnostics:
                print(f"{item.code}\t{item.severity}\t{item.summary}")
        return 20 if diagnostics else 0
    result = parse_mdrun_log(log)
    if command == "gromacs-energy":
        value = result.potential_energy_kj_mol if arguments.term is None else result.energies.get(arguments.term)
        if value is None:
            return BRIDGE_ABSENT
        print(f"{value * KJ_MOL_TO_EV if arguments.unit == 'ev' else value:.16g}")
        return 0
    if command == "gromacs-converged":
        return 0 if result.converged else BRIDGE_ABSENT
    raise AssertionError(command)
