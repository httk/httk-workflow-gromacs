#!/usr/bin/env bash

# Native httk GROMACS Bash API, version 1. Source httk-workflow.sh first.
#
# Every function is one gromacs-* bridge subcommand, and every option of that
# subcommand is available here: the arguments are passed through untouched.
#
#   httk_gromacs_run [--directory .] [--deffnm run] [--configuration conf.gro] [--topology topol.top]
#                    [--mdrun-options '-nt 1'] [--timeout S] -- gmx ...
#       runs grompp -f DEFFNM.mdp, then mdrun -deffnm DEFFNM; prints the report
#       path; exits 0 completed, 20 crashed, 21 nonconverged, 22 process
#       failure, 124 timeout
#   httk_gromacs_energy [--log run.log] [--term NAME] [--unit kj_mol|ev]   exits 1 when there is none
#   httk_gromacs_converged [--log run.log]          exits 1 when not a converged minimization
#   httk_gromacs_diagnose [--log run.log] [--json]  exits 20 when it found anything
HTTK_GROMACS_BASH_API_VERSION=1

_httk_gromacs_require_workflow_api() {
    if ! declare -F _httk_workflow_bridge >/dev/null 2>&1; then
        printf 'httk-workflow: source HTTK_WORKFLOW_BASH_API before HTTK_WORKFLOW_GROMACS_BASH_API\n' >&2
        return 2
    fi
}

httk_gromacs_run() {
    _httk_gromacs_require_workflow_api || return
    _httk_workflow_bridge gromacs-run "$@"
}

httk_gromacs_energy() {
    _httk_gromacs_require_workflow_api || return
    _httk_workflow_bridge gromacs-energy "$@"
}

httk_gromacs_converged() {
    _httk_gromacs_require_workflow_api || return
    _httk_workflow_bridge gromacs-converged "$@"
}

httk_gromacs_diagnose() {
    _httk_gromacs_require_workflow_api || return
    _httk_workflow_bridge gromacs-diagnose "$@"
}
