from __future__ import annotations

from pathlib import Path
import sys
import json
import os
import subprocess
import time
import httpx

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from Backend.Dal.models.provider import Provider
from Backend.Dal.models.article import Article

PERFORMANCE_EMAIL = "performance@vnaana.test"
PERFORMANCE_PASSWORD = "Vnaana-Performance-Test-2026!"
ROOT = Path(__file__).resolve().parents[2]
PERFORMANCE = ROOT / "tests" / "performance"
SUPABASE_WORKDIR = PERFORMANCE
FRONTEND = ROOT / "Frontend"
BACKEND = ROOT / "Backend"
AUTH_STATE = PERFORMANCE / "data" / "auth-state.json"
LHCI_BASE_URL = "http://localhost:5173"
CLI_VERSION = "3.3.0"


def run(command: list[str], *, cwd: Path = ROOT,
        env: dict[str, str] | None = None) -> None:
    print(f"\n> {' '.join(command)}", flush=True)

    if os.name == "nt":
        subprocess.run(
            subprocess.list2cmdline(command),
            cwd=cwd,
            env=env,
            check=True,
            shell=True,
        )
    else:
        subprocess.run(command, cwd=cwd, env=env, check=True)


def run_frontend_performance(status: dict) -> None:
    frontend_env = os.environ.copy()

    frontend_env.update({
        "VITE_API_BASE_URL": "http://127.0.0.1:8765",
        "VITE_SUPABASE_URL": status["API_URL"],
        "VITE_SUPABASE_PUBLISHABLE_KEY": status["PUBLISHABLE_KEY"],
    })

    print("\nBuilding production frontend...")
    run(["pnpm", "build"], cwd=FRONTEND, env=frontend_env)

    lighthouse_env = frontend_env.copy()
    lighthouse_env.update({
        "LHCI_BASE_URL": LHCI_BASE_URL,
        "LHCI_AUTH_STATE": str(AUTH_STATE.resolve()),
    })

    print("\nRunning Lighthouse CI...")
    run(
        ["pnpm", "test:performance"],
        cwd=FRONTEND,
        env=lighthouse_env,
    )
    print_lighthouse_results()


def supabase(*args: str) -> None:
    run(
        ["pnpm", "npx", "--yes", f"supabase@{CLI_VERSION}",
         *args, "--workdir", str(SUPABASE_WORKDIR)],
        cwd=FRONTEND,
    )


def start_backend(database_url: str, status: dict):
    backend_env = os.environ.copy()

    backend_env.update({
        "DATABASE_URL": database_url,
        "SUPABASE_URL": status["API_URL"],
        "SUPABASE_PUBLISHABLE_KEY": status["PUBLISHABLE_KEY"],
        "API_URL": "http://127.0.0.1:8765",
    })

    print("\nStarting performance backend...")

    process = subprocess.Popen(
        [
            sys.executable,
            "-m", "uvicorn",
            "Backend.main:app",
            "--host", "127.0.0.1",
            "--port", "8765",
        ],
        cwd=ROOT,
        env=backend_env,
    )

    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError("Performance backend stopped during startup.")

        try:
            response = httpx.get(
                "http://127.0.0.1:8765/tags",
                timeout=2,
            )
            if response.status_code < 500:
                print("Performance backend is ready.")
                return process
        except httpx.HTTPError:
            pass

        time.sleep(1)

    process.terminate()
    raise RuntimeError("Performance backend did not become ready.")

def print_lighthouse_results():
    report_dir = ROOT / ".lighthouseci"
    reports = sorted(report_dir.glob("lhr-*.json"))

    print("\n" + "=" * 65)
    print("FRONTEND PERFORMANCE RESULTS")
    print("=" * 65)

    if not reports:
        print("No Lighthouse JSON reports were found.")
        return

    for report in reports:
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
            audits = data.get("audits", {})
            categories = data.get("categories", {})

            url = data.get("requestedUrl", "Unknown URL")
            performance = categories.get("performance", {}).get("score")

            lcp = audits.get("largest-contentful-paint", {}).get("numericValue")
            tbt = audits.get("total-blocking-time", {}).get("numericValue")
            cls = audits.get("cumulative-layout-shift", {}).get("numericValue")

            print(f"\nURL: {url}")
            print(
                f"  Performance score: "
                f"{performance * 100:.0f}/100"
                if performance is not None
                else "  Performance score: unavailable"
            )
            print(f"  LCP: {lcp:.0f} ms" if lcp is not None else "  LCP: unavailable")
            print(f"  TBT: {tbt:.0f} ms" if tbt is not None else "  TBT: unavailable")
            print(f"  CLS: {cls:.3f}" if cls is not None else "  CLS: unavailable")

        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            print(f"Could not read {report.name}: {error}")

    print("\n" + "=" * 65)

def create_performance_user(status: dict) -> dict:
    api_url = status["API_URL"]
    service_key = status["SERVICE_ROLE_KEY"]
    publishable_key = status["PUBLISHABLE_KEY"]

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }

    with httpx.Client(
        base_url=f"{api_url}/auth/v1",
        headers=headers,
        timeout=30,
    ) as admin:
        # Reuse the dedicated account if it already exists.
        users_response = admin.get("/admin/users", params={"page": 1, "per_page": 100})
        users_response.raise_for_status()

        users = users_response.json().get("users", [])
        existing = next(
            (user for user in users if user["email"] == PERFORMANCE_EMAIL),
            None,
        )

        if existing:
            user_id = existing["id"]
            update = admin.put(
                f"/admin/users/{user_id}",
                json={
                    "password": PERFORMANCE_PASSWORD,
                    "email_confirm": True,
                },
            )
            update.raise_for_status()
        else:
            created = admin.post(
                "/admin/users",
                json={
                    "email": PERFORMANCE_EMAIL,
                    "password": PERFORMANCE_PASSWORD,
                    "email_confirm": True,
                },
            )
            created.raise_for_status()
            user_id = created.json()["id"]

    # Obtain a normal user session using the public key.
    with httpx.Client(
        base_url=f"{api_url}/auth/v1",
        headers={"apikey": publishable_key},
        timeout=30,
    ) as client:
        login = client.post(
            "/token",
            params={"grant_type": "password"},
            json={
                "email": PERFORMANCE_EMAIL,
                "password": PERFORMANCE_PASSWORD,
            },
        )
        login.raise_for_status()
        session_data = login.json()

    print("Performance test user authenticated successfully.")

    return {
        "user_id": user_id,
        "session": session_data,
    }


def get_supabase_status() -> dict:
    command = [
        "pnpm", "npx", "--yes", f"supabase@{CLI_VERSION}",
        "status", "--workdir", str(SUPABASE_WORKDIR), "-o", "json",
    ]

    if os.name == "nt":
        result = subprocess.run(
            subprocess.list2cmdline(command),
            cwd=FRONTEND,
            check=True,
            capture_output=True,
            text=True,
            shell=True,
        )
    else:
        result = subprocess.run(
            command,
            cwd=FRONTEND,
            check=True,
            capture_output=True,
            text=True,
        )

    output = result.stdout
    start = output.find("{")

    if start == -1:
        raise RuntimeError("Supabase status did not return JSON.")

    return json.loads(output[start:])


def get_performance_database_url(status: dict) -> str:
    database_url = status.get("DB_URL")

    if not database_url:
        raise RuntimeError("Supabase status did not contain DB_URL.")

    # The backend uses psycopg 3.
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        )

    return database_url


def apply_migrations(database_url: str) -> None:
    migration_env = os.environ.copy()

    # Explicitly target the isolated performance database.
    migration_env["DATABASE_URL"] = database_url

    print("\nApplying Alembic migrations to performance database...")
    run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=ROOT,
        env=migration_env,
    )
    print("Performance database migrations completed.")



def bootstrap_performance_user(user: dict, status: dict) -> None:
    api_url = "http://127.0.0.1:8765"
    access_token = user["session"]["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    with httpx.Client(
        base_url=api_url,
        headers=headers,
        timeout=30,
    ) as client:
        bootstrap = client.post("/users/me/bootstrap")
        bootstrap.raise_for_status()

        # Use the application profile ID, not the Supabase Auth ID.
        profile_id = bootstrap.json()["id"]

        client.put(
            f"/users/{profile_id}/consent",
            json={"analytics_consent": True},
        ).raise_for_status()

        client.put(
            f"/users/{profile_id}/onboarding",
            json={"onboarding_completed": True},
        ).raise_for_status()

    print("Performance user profile bootstrapped successfully.")


def create_browser_auth_state(status: dict) -> None:
    auth_env = os.environ.copy()
    auth_env["PERFORMANCE_SUPABASE_URL"] = status["API_URL"]
    auth_env["PERFORMANCE_SUPABASE_PUBLISHABLE_KEY"] = (
        status["PUBLISHABLE_KEY"]
    )

    print("\nCreating authenticated browser state...")

    run(
        [sys.executable, str(PERFORMANCE / "create_auth_state.py")],
        cwd=ROOT,
        env=auth_env,
    )


def seed_performance_data(database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        with Session(engine) as session:
            provider = session.query(Provider).filter_by(
                domain="performance.vnaana.test"
            ).first()

            if provider is None:
                provider = Provider(
                    name="Performance Test News",
                    domain="performance.vnaana.test",
                    reliability_status="verified",
                )
                session.add(provider)
                session.flush()

            for number in range(1, 11):
                canonical_url = (
                    f"https://performance.vnaana.test/articles/{number}"
                )

                article = session.query(Article).filter_by(
                    canonical_url=canonical_url
                ).first()

                if article is None:
                    article = Article(
                        provider_id=provider.id,
                        canonical_url=canonical_url,
                        title=f"Performance test article {number}",
                        description=(
                            f"Test article {number} for VNAANA performance testing."
                        ),
                        content=(
                            f"Performance testing article content. "
                            f"This is test article number {number}."
                        ),
                        author="Performance Test",
                        language="en",
                    )
                    session.add(article)

            session.commit()

        print("Performance test data seeded successfully.")

    finally:
        engine.dispose()




def main() -> None:
    print("Starting the dedicated performance Supabase project...")
    supabase("start")

    status = get_supabase_status()
    database_url = get_performance_database_url(status)

    print("\nPerformance Supabase is running.")
    print("Connection settings found:", ", ".join(sorted(status.keys())))

    apply_migrations(database_url)
    seed_performance_data(database_url)

    backend = start_backend(database_url, status)

    try:
        user = create_performance_user(status)
        bootstrap_performance_user(user, status)
        create_browser_auth_state(status)

        print("\nPerformance database and backend are ready.")

        run_frontend_performance(status)

        print("\nFrontend performance testing completed.")

    finally:
        print("\nStopping performance backend...")
        backend.terminate()

        try:
            backend.wait(timeout=10)
        except subprocess.TimeoutExpired:
            backend.kill()
            backend.wait()



if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"\nCommand failed with exit code {exc.returncode}.", file=sys.stderr)
        raise SystemExit(exc.returncode)
