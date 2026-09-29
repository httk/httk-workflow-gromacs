# Test data

Captured GROMACS 2026.3 (conda-forge, `nompi`, `OMP_NUM_THREADS=1`) runs of a
tiny box of eight argon atoms described by a custom Lennard-Jones atom type
(`ar.top`). Every run used `gmx grompp -f X.mdp -c X.gro -p ar.top -o X.tpr`
and `gmx mdrun -deffnm X -nt 1`.

| File | What it is |
| --- | --- |
| `ar.gro`, `ar.top`, `em.mdp`, `em.log` | converged steepest-descent minimization: `Steepest Descents converged to Fmax < 100 in 1 steps`, `Potential Energy  = -1.3482650e+01`, `Finished mdrun` |
| `ar_perturbed.gro`, `em_noconv.mdp`, `em_noconv.log` | atom 2 displaced, `nsteps = 2`, `emtol = 0.001`: `Steepest Descents did not converge to Fmax < 0.001 in 3 steps.`, exit status 0 |
| `em_machine_precision.mdp`, `em_machine_precision.log` | `ar_perturbed.gro` with `emtol = 1e-12`: `Steepest Descents converged to machine precision in 94 steps, but did not reach the requested Fmax < 1e-12.`, exit status 0 |
| `md.mdp`, `md.log` | 50 steps of NVT dynamics (`integrator = md`, v-rescale at 100 K): energies tables of two rows (`Potential`, `Kinetic En.`, `Total Energy`, `Conserved En.`, `Temperature`, ...) and a run-averages section |
| `ar_small_box.gro`, `grompp_fatal.err` | the box shrunk to 1.5 nm: `grompp`'s standard error with `ERROR 1 [file ar.top, line 23]: ... The cut-off length is longer than half the shortest box vector ...` and the `Fatal error:` block, exit status 1 |

The `.gro`, `.top` and `.mdp` files were written for these tests; the logs and
standard error are program output of those runs, with the absolute paths of the
capture machine replaced by `/opt/gromacs` (installation) and `/scratch/gromacs`
(working directories).
