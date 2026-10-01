"""Recognize hook for ``gromacs.calculation``: one mdrun log with its run input beside it."""

import hashlib
from pathlib import Path, PurePath

from httk.core.datastream.compression import split_compression_suffix
from httk.workflow.calculations import content_digest
from httk.workflow.collecting import existing_file
from httk.workflow.hookapi import Claim, Unclaimed

from httk.codes.gromacs.collect import find_outputs, read_command_line


def _identity_options(command: str | None) -> str:
    """The physics-relevant part of an ``mdrun`` command line, normalised; ``""`` when there is none."""

    tokens = command.split() if command else []
    kept: list[str] = []
    for index, token in enumerate(tokens):
        value = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token == "-nsteps":
            kept.append(f"-nsteps {value}")
        elif token in ("-rerun", "-plumed"):
            kept.append(f"{token} {PurePath(value).name}")
        elif token == "-cpi":
            kept.append("-cpi")
    return " ".join(sorted(kept))


def recognize(directory: Path) -> Claim | Unclaimed | None:
    """Claim a directory holding exactly one mdrun log and its run input.

    :param directory: The directory to examine.
    :return: A claim identified by the ``.tpr`` (else the ``.mdp``) content and the logged command line, ``Unclaimed``
        for a GROMACS directory that cannot be collected, or ``None`` when it holds no mdrun log.
    """

    outputs = list(find_outputs(directory))
    if not outputs:
        return None
    if len(outputs) > 1:
        return Unclaimed(f"several GROMACS mdrun logs: {', '.join(path.name for path in outputs)}")
    output = outputs[0]
    stem = PurePath(split_compression_suffix(output.name)[0]).stem
    for name in (f"{stem}.tpr", f"{stem}.mdp"):
        if existing_file(directory / name) is not None:
            digest = content_digest(directory, [name])
            options = _identity_options(read_command_line(output))
            if options:
                # A rerun from the same input with other physics options (-nsteps, -cpi) is another calculation.
                digest = hashlib.sha256(f"{digest}\0{options}".encode()).hexdigest()
            return Claim(digest)
    return Unclaimed(f"no {stem}.tpr or {stem}.mdp beside {output.name}")
