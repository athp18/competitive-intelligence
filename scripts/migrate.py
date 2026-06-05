#!/usr/bin/env python3
"""Run Alembic migrations then start the API. Used in Railway startup."""
import subprocess
import sys


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    run(["alembic", "upgrade", "head"])
    print("Migrations complete.")
