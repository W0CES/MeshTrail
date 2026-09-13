"""Verify that the installed wheel works in a clean Linux container."""

from __future__ import annotations

import tempfile
from importlib.resources import files
from pathlib import Path

from meshtrail_plugin.game import TrailStore


def main() -> None:
    logo = files("meshtrail_plugin").joinpath("assets/meshtrail-logo.png")
    if not logo.is_file():
        raise RuntimeError("packaged MeshTrail logo is missing")

    with tempfile.TemporaryDirectory(prefix="meshtrail-smoke-") as directory:
        database = Path(directory) / "meshtrail.sqlite3"
        game = TrailStore(database, random_seed=1848)
        opening = game.handle("container-player", "start", timestamp=1)
        river = game.handle("container-player", "go", timestamp=2)
        crossing = game.handle("container-player", "ferry", timestamp=3)
        resumed = TrailStore(database, random_seed=1848)
        status = resumed.handle("container-player", "status", timestamp=4)

    if not opening or "rabbit seal" not in opening:
        raise RuntimeError(f"unexpected opening: {opening!r}")
    if not river or "Kansas River" not in river:
        raise RuntimeError(f"unexpected first travel result: {river!r}")
    if not crossing or "safely across" not in crossing:
        raise RuntimeError(f"unexpected crossing result: {crossing!r}")
    if not status or "55/2000mi" not in status:
        raise RuntimeError(f"SQLite state did not survive restart: {status!r}")
    print("MeshTrail container smoke test passed")


if __name__ == "__main__":
    main()

