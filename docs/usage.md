# Using the GROMACS helpers

*httk-workflow-gromacs* ships the GROMACS helpers that workflow runners are
built on, in two languages: the Python package {py:mod}`httk.codes.gromacs` and
the Bash GROMACS API, whose `httk_gromacs_*` functions call the same code
through the *httk-workflow* shell bridge.

## Install

```console
python -m pip install httk-workflow-gromacs
```

The distribution depends on *httk-core* and *httk-workflow*. Installing it
registers the `gromacs` code through the `httk.registry.codes.gromacs`
registration package, which makes the `gromacs-*` bridge commands and the Bash
API available to every job the manager starts; nothing needs to be configured.
GROMACS is a classical molecular-dynamics code, so the module writes no inputs:
the configuration (`.gro`), topology (`.top`) and run parameters (`.mdp`) are
prepared by you.

## Python

```python
from httk.codes.gromacs import run_gromacs

report = run_gromacs(
    grompp_argv=["gmx", "grompp", "-f", "run.mdp", "-c", "conf.gro", "-p", "topol.top", "-o", "run.tpr"],
    mdrun_argv=["gmx", "mdrun", "-deffnm", "run", "-nt", "4"],
    timeout=3600,
)
if report.ok:
    print(report.result.potential_energy_kj_mol, report.result.energies.get("Temperature"))
else:
    print(report.classification, [item.code for item in report.diagnostics])
```

- {py:func}`~httk.codes.gromacs.parse_mdrun_log` returns a
  {py:class}`~httk.codes.gromacs.GromacsResult`: the final potential energy
  (kJ/mol, and eV through `potential_energy_ev`), the last instantaneous
  `Energies (kJ/mol)` table as a name-to-value mapping (the run-averages table
  is not used), whether an energy minimization converged (`None` for dynamics),
  the step count, whether `Finished mdrun` was reached, and the `Fatal error`
  messages.
- {py:func}`~httk.codes.gromacs.parse_fatal_errors` extracts `grompp`'s
  numbered input errors and the `Fatal error:` messages from any GROMACS output
  text, such as a saved standard error.
- {py:func}`~httk.codes.gromacs.run_gromacs` runs `grompp` and then `mdrun`
  under the *httk-workflow* process supervisor, saves each step's standard
  output and error as `grompp.out`/`grompp.err` and `mdrun.out`/`mdrun.err`,
  and returns a {py:class}`~httk.codes.gromacs.GromacsRunReport` classified as
  `completed`, `crashed`, `nonconverged`, `process_failure` or `timeout`, also
  written to `gromacs-run-report.json`. `mdrun` runs only when `grompp`
  succeeded; a failed `grompp` is `crashed`.
- {py:func}`~httk.codes.gromacs.diagnose_gromacs` diagnoses a finished run.

## Diagnostics

| Code | Severity | Meaning |
| --- | --- | --- |
| `gromacs.fatal` | fatal | `grompp` or `mdrun` stopped with an error message (in the log, `grompp.err` or `mdrun.err`); the summary is the message |
| `gromacs.em_not_converged` | error | an energy minimization reported `did not converge to Fmax`, or `converged to machine precision` short of the requested Fmax |
| `gromacs.incomplete` | error | no `Finished mdrun` line and no error message, e.g. a killed process |

A completed run has no diagnostics. A timed-out `mdrun` stops gracefully and
still writes `Finished mdrun`, so its log reads as completed and
`diagnose_gromacs` (and `httk_gromacs_diagnose`) reports nothing: the run
report's `timeout` classification is the authority on a timeout.

## Bash

The manager exports the path of the GROMACS API as
`HTTK_WORKFLOW_GROMACS_BASH_API` when *httk-workflow-gromacs* is installed, so
a Bash runner guards it and sources it after the generic library:

```bash
source "$HTTK_WORKFLOW_BASH_API"
: "${HTTK_WORKFLOW_GROMACS_BASH_API:?install httk-workflow-gromacs}"
source "$HTTK_WORKFLOW_GROMACS_BASH_API"

httk_gromacs_run --mdrun-options='-nt 4' --timeout 3600 -- gmx   # grompp -f run.mdp -c conf.gro -p topol.top
energy=$(httk_gromacs_energy --unit ev)
temperature=$(httk_gromacs_energy --term Temperature)
```

| Function | Bridge command | Exit status |
| --- | --- | --- |
| `httk_gromacs_run [--directory .] [--deffnm run] [--configuration conf.gro] [--topology topol.top] [--mdrun-options=OPTS] [--timeout S] -- GMX...` | `gromacs-run` | `0` completed, `20` crashed, `21` nonconverged, `22` process failure, `124` timeout (as `vasp-run`); prints the report path |
| `httk_gromacs_energy [--log run.log] [--term NAME] [--unit kj_mol\|ev]` | `gromacs-energy` | `0` and the potential energy (or the named energies-table term), `1` when there is none |
| `httk_gromacs_converged [--log run.log]` | `gromacs-converged` | `0` a converged minimization, `1` not converged, dynamics or unknown |
| `httk_gromacs_diagnose [--log run.log] [--json]` | `gromacs-diagnose` | `0` clean, `20` when it printed diagnostics |

`httk_gromacs_run` runs `GMX grompp -f DEFFNM.mdp -c CONFIGURATION -p TOPOLOGY
-o DEFFNM.tpr` and then `GMX mdrun -deffnm DEFFNM OPTS`: the run-parameter file
name is derived from `--deffnm` (default `run.mdp`) and has no option of its
own. `--unit ev` converts kJ/mol to eV per particle (1 kJ/mol = 0.010364269656262175 eV). A refused call
(for example a missing log) exits `2`. `HTTK_GROMACS_BASH_API_VERSION` is `1`.

## The example workflow

The repository's `workflows/gromacs-run` is the workflow package `gromacs.run`:
one Python runner step that stages the `configuration`, `topology` and
`parameters` inputs as `conf.gro`, `topol.top` and `run.mdp`, runs `grompp` and
`mdrun -deffnm run`, and fails with the first diagnostic code when the run is
not clean. Install it with `httk plugin install` of the repository, or use it
directly with `--workflow-dir`:

```console
httk workspace settings set --key gromacs.command --value gmx_mpi WORKSPACE
httk job new --workflow gromacs.run --input configuration=conf.gro \
    --input topology=topol.top --input parameters=em.mdp
httk workflow run
httk collect --into results.sqlite
```

The settings `gromacs.command` (default `gmx`) and `gromacs.mdrun_options`
(default `-nt 1`) say how to start GROMACS and what to pass to `mdrun`. The
results stay in the job's persistent workdir (`run.log`, `run.edr`, `run.gro`,
...).

## Collecting

`gromacs.run` declares no outputs and has no collector, so collecting it is
*run-only*: `httk collect --into` stores one provenance `runs` entry
per job and no data records. The energies are still in the workdir's `run.log`
for {py:func}`~httk.codes.gromacs.parse_mdrun_log`.

### Recognized calculations

A finished `mdrun` that was not started by a workspace is collected by the
registered `gromacs.calculation` collector:
`httk.workflow.collect_tree(root)` finds every directory holding exactly one
`<stem>.log` whose first 100 lines carry the banner `GROMACS - gmx mdrun`
together with `<stem>.tpr` (else `<stem>.mdp`), compressed or not, and collects
its `average_total_energy`. The value is GROMACS's own printed average: the
`Total Energy` of the last `A V E R A G E S` section of the log, in eV. The
identity is a digest of the `.tpr` (else the `.mdp`) and the physics options of the
`Command line:` the log records: `-nsteps`, the basenames of `-rerun` and
`-plumed`, and whether `-cpi` is present (a continuation). The program name,
paths, thread and performance options are ignored, so the same run on another
machine keeps its identity, as does moving the directory. A log without such
options is identified by the input alone. Of an appended continuation log only
the last part (after its last banner) is judged, so a part that died before
finishing is degraded. The part logs of a `-noappend` continuation are several logs and
are reported as unclaimed. A directory with several mdrun logs or without the run input is
reported as unclaimed; an energy minimisation or unfinished run has no averages
and is claimed and degraded.
{py:func}`~httk.codes.gromacs.collect.find_outputs` is the same banner-based finder.
