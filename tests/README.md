# Tests

All tests live here and run with one command from the repository root:

```powershell
python -m pytest
```

| Folder | What | Needs |
|---|---|---|
| `backend/unit` | Backend logic, fake repositories, no database | Python packages |
| `backend/integration` | DAL against the real migrated Postgres database | Local Supabase (below) |
| `backend/security` | Login checks and rate limiting through the whole app, services faked | Python packages |
| `backend/manual` | Scripts for a real database or Ollama, never collected by pytest | Run by hand with `python -m tests.backend.manual.<name>` |
| `frontend` | Frontend unit tests (`node --test`), started from pytest | Node.js 22+, `npm ci` in `Frontend/` |
| `e2e` | Browser tests through the whole app (Playwright) | Everything below |

A test that can't run because something is missing is **skipped** with the reason, so `python -m pytest -rs` shows what to install or start. In CI, `REQUIRE_ALL_TESTS=1` turns every skip into a failure.

## One-time setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
cd Frontend; npm ci; cd ..
```

For the integration and E2E tests also install [Docker Desktop](https://docs.docker.com/desktop/).

## Local Supabase (integration and E2E tests)

The integration and E2E tests run against a **local** Supabase (database + Auth in Docker), never the team's cloud project. Start it once; it keeps running between test runs:

```powershell
npx supabase@3 start --workdir tests/e2e
```

The first start downloads the Docker images and takes a few minutes. Stop it with `npx supabase@3 stop --workdir tests/e2e`.

## Integration tests

The integration tests use their own database, `vnaana_integration`, on that local Postgres. Every run drops it, creates it again and builds it with the real Alembic migrations, so the tests see exactly the tables, constraints and seeded rows (default tags, event weights) production gets. Each test runs in a transaction that is rolled back afterwards, so nothing is left behind and the E2E data is never touched.

## E2E tests

Every run does the rest by itself:

1. Drops the app's tables and rebuilds them with the real Alembic migrations (tags come from a migration).
2. Adds 5 test articles and removes every local account.
3. Creates the test account `e2e@vnaana.test` through the Supabase admin API.
4. Starts the API on port 8765 and Vite on port **5173** (the only origin the API's CORS allows), both pointed at the local Supabase. Your own `Backend/.env` and `Frontend/.env.local` are overridden for these servers.

So stop your own Vite dev server before running the E2E tests.

Not covered by E2E: Google sign-in (Google blocks automated browsers; the frontend unit tests cover our Google code) and Nova/Ollama (covered by the backend unit tests).

Useful while writing E2E tests:

```powershell
python -m pytest tests/e2e --headed --slowmo 500   # watch the browser
python -m pytest tests/e2e --tracing retain-on-failure   # then: playwright show-trace test-results/.../trace.zip
```
