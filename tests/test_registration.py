"""The ``gromacs`` code is registered through the ``codes`` registry tier, with its citation."""

import argparse
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import httk.core  # noqa: F401  (importing httk.core runs registry discovery)
from httk.core.register import code_support, known_codes


def test_gromacs_is_a_known_code_with_its_packaged_bash_api() -> None:
    assert "gromacs" in known_codes()
    expected = Path(str(files("httk.codes.gromacs").joinpath("httk-gromacs.sh")))
    assert code_support("gromacs").bash_api_path() == expected


def test_the_bridge_mounts_the_gromacs_commands() -> None:
    parser = argparse.ArgumentParser()
    code_support("gromacs").resolve_bridge().add_commands(parser.add_subparsers(dest="command"))
    assert parser.parse_args(["gromacs-energy"]).command == "gromacs-energy"


def test_the_gromacs_credit_is_registered_on_import() -> None:
    script = """
from httk.core import credits
assert "Calculations with GROMACS" not in credits.entries()
import httk.codes.gromacs
assert len(credits.entries()["Calculations with GROMACS"]) == 1
"""
    subprocess.run([sys.executable, "-c", script], check=True)
