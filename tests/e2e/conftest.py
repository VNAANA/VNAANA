"""Fixtures for the end-to-end tests.

Needs local Supabase (database + Auth in Docker), started once from the repository root:

    npx supabase@3 start --workdir tests/e2e

Everything else is done here for every run: a clean database through the real
migrations, test articles, a test account, and the API and Vite pointed at the
local Supabase. Without local Supabase every E2E test is skipped.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from Backend.Dal.models import Article, Base, Provider, Story, StoryArticle, StoryStatus
from tests.e2e.support import (
    API_PORT,
    API_URL,
    STORY_TITLES,
    FRONTEND_URL,
    SEEDED_STORY,
    TEST_EMAIL,
    TEST_PASSWORD,
    log_in,
)

ROOT = Path(__file__).resolve().parents[2]
E2E = ROOT / "tests" / "e2e"
FRONTEND = ROOT / "Frontend"
START_SUPABASE = "run `npx supabase@3 start --workdir tests/e2e` first"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def port_in_use(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def supabase() -> dict[str, str]:
    """URLs and keys of the local Supabase, read from the Supabase CLI."""
    if not port_in_use("127.0.0.1", 54321):
        pytest.skip(f"Local Supabase is not running: {START_SUPABASE}")
    npx = shutil.which("npx")
    if npx is None:
        pytest.skip("npx not found: install Node.js 22+")

    result = subprocess.run(
        [npx, "--yes", "supabase@3", "status", "-o", "json", "--workdir", str(E2E)],
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
    # The fixtures below delete data, so they may only ever touch this machine.
    for url in (keys["api_url"], keys["db_url"]):
        host = urllib.parse.urlsplit(url).hostname
        if host not in LOCAL_HOSTS:
            pytest.fail(f"Refusing to run the E2E tests against a non-local Supabase ({host}).", pytrace=False)
    return keys


@pytest.fixture(scope="session")
def database(supabase):
    """A clean database built by the real migrations, with the test stories in it."""
    engine = create_engine(supabase["db_url"])

    # Drop the app's tables (not Supabase's own) and rebuild them with Alembic.
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT, env={**os.environ, "DATABASE_URL": supabase["db_url"]},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if migration.returncode != 0:
        pytest.fail(f"`alembic upgrade head` failed:\n{migration.stderr[-3000:]}", pytrace=False)

    # Tags come from a migration; the feed shows published stories, each led
    # by one article, so add those here.
    with Session(engine) as db:
        provider = Provider(name="E2E News", domain="e2e.vnaana.test", reliability_status="verified")
        db.add(provider)
        db.flush()
        for number, title in enumerate(STORY_TITLES, start=1):
            article = Article(
                provider_id=provider.id,
                canonical_url=f"https://e2e.vnaana.test/articles/{number}",
                title=f"E2E article {number}",
                description=f"Seeded article {number} for the end-to-end tests.",
            )
            story = Story(
                title=title,
                context=f"Background for seeded story {number}.",
                status=StoryStatus.published,
                first_published_at=datetime.now(timezone.utc),
            )
            db.add_all([article, story])
            db.flush()
            db.add(StoryArticle(story_id=story.id, article_id=article.id, is_primary=True))
        db.commit()

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_user(supabase, database) -> dict[str, str]:
    """Removes every local account, then creates the shared test account."""
    key = supabase["service_role_key"]
    with httpx.Client(
        base_url=f"{supabase['api_url']}/auth/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    ) as admin:
        listing = admin.get("/admin/users", params={"per_page": 1000})
        listing.raise_for_status()
        for user in listing.json()["users"]:
            admin.delete(f"/admin/users/{user['id']}").raise_for_status()

        created = admin.post(
            "/admin/users",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True},
        )
        created.raise_for_status()
    return {"email": TEST_EMAIL, "password": TEST_PASSWORD}


def start(command: list[str], cwd: Path, env: dict[str, str], log: Path) -> subprocess.Popen:
    log_file = log.open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log_file, stderr=subprocess.STDOUT)
    process.log_file = log_file
    process.log_path = log
    return process


def wait_until_up(url: str, process: subprocess.Popen, name: str, seconds: int = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    process.log_file.flush()
    output = process.log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
    pytest.fail(f"{name} did not start at {url}. Its output:\n{output}", pytrace=False)


def stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    process.log_file.close()


@pytest.fixture(scope="session")
def servers(supabase, database, tmp_path_factory):
    """Starts the API and Vite against the local Supabase, and stops them afterwards."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not found: install Node.js 22+")
    vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite.exists():
        pytest.skip("Frontend packages missing: run `npm ci` in Frontend/")
    for port, owner in ((5173, "Vite dev server"), (API_PORT, "process")):
        if port_in_use("localhost", port) or port_in_use("127.0.0.1", port):
            pytest.fail(f"Port {port} is already in use: stop your own {owner} first.", pytrace=False)

    logs = tmp_path_factory.mktemp("e2e-logs")
    # Environment variables win over Backend/.env and Frontend/.env.local, so
    # neither server can end up talking to the team's cloud Supabase.
    api = start(
        [sys.executable, "-m", "uvicorn", "Backend.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
        ROOT,
        {
            **os.environ,
            "DATABASE_URL": supabase["db_url"],
            "SUPABASE_URL": supabase["api_url"],
            "SUPABASE_PUBLISHABLE_KEY": supabase["publishable_key"],
            # Every E2E request comes from 127.0.0.1, and one page load already
            # makes several API calls; the real limit would make runs flaky.
            "RATE_LIMIT": "1000/minute",
        },
        logs / "api.log",
    )
    web = start(
        [node, str(vite), "--port", "5173", "--strictPort", "--host", "localhost"],
        FRONTEND,
        {
            **os.environ,
            "VITE_API_BASE_URL": API_URL,
            "VITE_SUPABASE_URL": supabase["api_url"],
            "VITE_SUPABASE_PUBLISHABLE_KEY": supabase["publishable_key"],
        },
        logs / "vite.log",
    )
    try:
        wait_until_up(f"{API_URL}/tags", api, "The API")
        wait_until_up(FRONTEND_URL, web, "Vite")
        yield
    finally:
        stop(web)
        stop(api)


@pytest.fixture(autouse=True)
def e2e_stack(servers):
    """Every E2E test needs the whole stack running."""


@pytest.fixture(scope="session")
def ready_user(supabase, test_user, servers) -> dict[str, str]:
    """The test account with consent given and onboarding done, through our own API."""
    token = httpx.post(
        f"{supabase['api_url']}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": supabase["publishable_key"]},
        json={"email": test_user["email"], "password": test_user["password"]},
        timeout=30,
    )
    token.raise_for_status()
    with httpx.Client(
        base_url=API_URL,
        headers={"Authorization": f"Bearer {token.json()['access_token']}"},
        timeout=30,
    ) as api:
        profile = api.post("/users/me/bootstrap")
        profile.raise_for_status()
        user_id = profile.json()["id"]
        api.put(f"/users/{user_id}/consent", json={"analytics_consent": True}).raise_for_status()
        api.put(f"/users/{user_id}/onboarding", json={"onboarding_completed": True}).raise_for_status()
    return test_user


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # English labels (the app follows the browser language) and relative page.goto() paths.
    return {**browser_context_args, "locale": "en-GB", "base_url": FRONTEND_URL}


@pytest.fixture(scope="session")
def logged_in_state(browser, browser_context_args, ready_user, tmp_path_factory) -> Path:
    """Logs in once through the login form and saves the session for the other tests."""
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    log_in(page, ready_user["email"], ready_user["password"])
    expect(page.get_by_role("article", name=SEEDED_STORY).first).to_be_visible()
    state = tmp_path_factory.mktemp("auth") / "state.json"
    context.storage_state(path=state)
    context.close()
    return state


@pytest.fixture
def logged_in_page(browser, browser_context_args, logged_in_state):
    context = browser.new_context(**browser_context_args, storage_state=logged_in_state)
    page = context.new_page()
    yield page
    context.close()
