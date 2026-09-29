# *httk-workflow-gromacs*

This site documents the *httk-workflow-gromacs* module. For the full
documentation of *httk₂*, see [docs.httk.org](https://docs.httk.org).

The module adds GROMACS support to *httk-workflow*: the Python helpers in
`httk.codes.gromacs` (log parsing, diagnostics and supervised `grompp` +
`mdrun` execution), the Bash API a Bash runner sources as
`$HTTK_WORKFLOW_GROMACS_BASH_API`, and the `gromacs-*` bridge commands behind
that API. Installing it registers the `gromacs` code with *httk₂* through the
`httk.registry.codes.gromacs` registration package. The repository also carries
the example workflow package `gromacs.run`.

```{admonition} Quick links
:class: tip

- {doc}`usage` — the Python and Bash API, the example workflow, and the diagnostics
- {doc}`reference/index` — the generated API reference
```

## Install

```console
python -m pip install httk-workflow-gromacs
```

```{toctree}
:maxdepth: 2
:caption: Documentation

usage
reference/index
```
