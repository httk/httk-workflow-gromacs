# httk-workflow-gromacs

![Status: Early beta](https://img.shields.io/badge/status-early--beta-orange)

> **⚠️ EARLY BETA**
>
> This is an early beta release of *httk₂*. The organization of the packages
> and their APIs should not yet be regarded as stable, and may change between
> releases.

*httk-workflow-gromacs* adds GROMACS support to
[*httk-workflow*](https://github.com/httk/httk-workflow), the workflow engine of
[*httk₂*](https://github.com/httk/httk2). It provides `httk.codes.gromacs`:
parsing the `mdrun` log and GROMACS error messages, stable diagnostics, and
supervised `grompp` + `mdrun` execution with a classified run report; and the
Bash API that exposes the same helpers to Bash runners. Installing it registers
the `gromacs` code with *httk₂*; nothing needs to be configured.

## Install

```console
python -m pip install httk-workflow-gromacs
```

## Use

In a Python runner:

```python
from httk.codes.gromacs import run_gromacs

report = run_gromacs(
    grompp_argv=["gmx", "grompp", "-f", "run.mdp", "-c", "conf.gro", "-p", "topol.top", "-o", "run.tpr"],
    mdrun_argv=["gmx", "mdrun", "-deffnm", "run"],
)
print(report.classification, report.result.potential_energy_kj_mol)
```

In a Bash runner, whose manager exports the path of the GROMACS API:

```bash
source "$HTTK_WORKFLOW_BASH_API"
: "${HTTK_WORKFLOW_GROMACS_BASH_API:?install httk-workflow-gromacs}"
source "$HTTK_WORKFLOW_GROMACS_BASH_API"
httk_gromacs_run -- gmx
energy=$(httk_gromacs_energy --unit ev)
```

A complete example workflow package, `gromacs.run`, is in
[`workflows/gromacs-run`](workflows/gromacs-run); `httk plugin install` of this
repository installs it. The API is documented in [`docs/usage.md`](docs/usage.md)
and at [docs.httk.org/httk-workflow-gromacs](https://docs.httk.org/httk-workflow-gromacs/).

## Running tests

`make test` runs the normal profile; `make ci` runs formatting, lint, both type
checkers and the extended tests. The end-to-end test runs the real `gmx` only
when `HTTK_TEST_GROMACS_COMMAND` names it or `gmx` is on `PATH`, and skips
otherwise.
