"""Register the GROMACS code support implemented by :mod:`httk.codes.gromacs`."""

from httk.core.register import register_code, register_collector

register_code("gromacs", bridge="httk.codes.gromacs._bridge", bash_api="httk.codes.gromacs:httk-gromacs.sh")
register_collector("gromacs.calculation", package="httk.codes.gromacs:collectors/gromacs")
