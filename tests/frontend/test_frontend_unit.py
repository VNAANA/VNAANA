"""Runs the frontend unit tests (node --test) so `python -m pytest` covers them too."""

import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "Frontend"


def test_frontend_unit_tests():
    npm = shutil.which("npm")
    if npm is None:
        pytest.skip("npm not found: install Node.js 22+ to run the frontend tests")
    if not (FRONTEND / "node_modules").is_dir():
        pytest.skip("Frontend packages missing: run `npm ci` in Frontend/")

    result = subprocess.run(
        [npm, "test"],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )

    if result.returncode != 0:
        pytest.fail(
            "Frontend tests failed. Run `npm test` in Frontend/ for the full output.\n\n"
            + result.stdout[-4000:]
            + result.stderr[-2000:],
            pytrace=False,
        )
