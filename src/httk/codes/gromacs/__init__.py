"""GROMACS support for *httk₂* workflows: the *httk-workflow-gromacs* package.

``outputs`` parses the ``mdrun`` log and GROMACS error messages,
``diagnostics`` classifies a finished run, and ``reports`` runs ``grompp`` and
``mdrun`` under supervision. This package is a thin facade re-exporting their
surface. The example workflow package ``workflows/gromacs-run`` in this
distribution's repository builds on it.
"""

from httk.core import register_citation

register_citation(
    applies_to="Calculations with GROMACS",
    references=(
        {
            "authors": ({"name": "Mark James Abraham"},),
            "note": "Abraham et al.; the DOI record lists every author",
            "title": (
                "GROMACS: High performance molecular simulations through multi-level parallelism "
                "from laptops to supercomputers"
            ),
            "journal": "SoftwareX",
            "volume": "1-2",
            "pages": "19-25",
            "year": "2015",
            "doi": "10.1016/j.softx.2015.06.001",
            "bib_type": "article",
        },
    ),
)

from .diagnostics import diagnose_gromacs
from .outputs import KJ_MOL_TO_EV, GromacsResult, parse_fatal_errors, parse_mdrun_log
from .reports import GromacsRunReport, run_gromacs

__all__ = [
    "KJ_MOL_TO_EV",
    "GromacsResult",
    "GromacsRunReport",
    "diagnose_gromacs",
    "parse_fatal_errors",
    "parse_mdrun_log",
    "run_gromacs",
]
