"""The local Supabase stack, shared by the integration and E2E tests.

Started once from the repository root (needs Docker):

    npx supabase@3 start --workdir tests/e2e

Both test sets read its URLs and keys from the Supabase CLI, refuse to touch
anything that isn't on this machine, and build their tables with the real
Alembic migrations. Without local Supabase the tests that need it skip.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUPABASE_WORKDIR = ROOT / "tests" / "e2e"
START_SUPABASE = "run `npx supabase@3 start --workdir tests/e2e` first"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def port_in_use(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def read_local_supabase() -> dict[str, str]:
    """URLs and keys of the local Supabase; skips when it isn't running."""
    if not port_in_use("127.0.0.1", 54321):
        pytest.skip(f"Local Supabase is not running: {START_SUPABASE}")
    npx = shutil.which("npx")
    if npx is None:
        pytest.skip("npx not found: install Node.js 22+")

    result = subprocess.run(
        [npx, "--yes", "supabase@3", "status", "-o", "json", "--workdir", str(SUPABASE_WORKDIR)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if result.returncode != 0 or "{" not in result.stdout:
        pytest.skip(f"Could not read the local Supabase status, {START_SUPABASE}\n{result.stderr[-500:]}")
    status = json.loads(result.stdout[result.stdout.index("{"): result.stdout.rindex("}") + 1])

    keys = {
        "api_url": status["API_URL"],
        "db_url": status["DB_URL"].replace("postgresql://", "postgresql+psycopg://", 1),
        "publishable_key": status.get("PUBLISHABLE_KEY") or status["ANON_KEY"],
        "service_role_key": status["SERVICE_ROLE_KEY"],
    }
    # The tests delete data, so they may only ever touch this machine.
    for url in (keys["api_url"], keys["db_url"]):
        host = urllib.parse.urlsplit(url).hostname
        if host not in LOCAL_HOSTS:
            pytest.fail(f"Refusing to run tests against a non-local Supabase ({host}).", pytrace=False)
    return keys


def migrate(db_url: str) -> None:
    """Build the app's tables with the real migrations (`alembic upgrade head`)."""
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT, env={**os.environ, "DATABASE_URL": db_url},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if migration.returncode != 0:
        pytest.fail(f"`alembic upgrade head` failed:\n{migration.stderr[-3000:]}", pytrace=False)
