# VNAANA performance tests

This folder contains two deliberately separate suites:

- `frontend/`: repeatable production-build audits with Lighthouse CI.
- `locustfile.py`: a manually started, read-only API load profile.

## 1. Frontend performance (automated)

The Lighthouse configuration audits six hash routes: login, sign-up, feed,
explore, profile settings, and profile topics. Protected routes require a
Playwright storage-state JSON file.

### Prerequisites

- Local Supabase, started from the repository root:
  `npx --yes supabase@3 start --workdir tests/e2e`
- Backend running at `http://127.0.0.1:8765`.
- Frontend dependencies installed, including `@lhci/cli` and `puppeteer`.
- A production build served at `http://localhost:5173`.
- `LHCI_AUTH_STATE` pointing to a Playwright storage-state file created by
  the existing `logged_in_state` fixture.
- The storage state's origin must be `http://localhost:5173`, matching the
  production preview origin. Do not use a different port: Supabase auth
  localStorage is origin-scoped.

Build the frontend with the same local API and Supabase values used by the
E2E fixtures:

```powershell
$env:VITE_API_BASE_URL = "http://127.0.0.1:8765"
$env:VITE_SUPABASE_URL = "<local Supabase API URL>"
$env:VITE_SUPABASE_PUBLISHABLE_KEY = "<local publishable/anon key>"
pnpm --dir Frontend build
```

Start the backend with the local Supabase environment (never the cloud
`.env` values):

```powershell
uvicorn Backend.main:app --host 127.0.0.1 --port 8765
```

Set the auth-state path and run Lighthouse from `Frontend/`:

```powershell
$env:LHCI_AUTH_STATE = "<absolute path to Playwright state.json>"
pnpm exec lhci autorun --config=../tests/performance/frontend/lighthouserc.cjs
```

The current E2E `logged_in_state` fixture creates a temporary state file.
For repeatable runs, add a small targeted E2E test that copies that fixture
to a stable path supplied through `LHCI_AUTH_STATE`, then run Lighthouse
while the local backend remains available. The preview and the state file
must use the same origin.

### Initial thresholds

Assertions are warnings initially, not build failures. Establish a baseline
on CI first; tighten thresholds after several stable runs. The report files
are written to `.lighthouseci/` and should be uploaded as CI artifacts.

## 2. Backend load tests (manual)

The Locust profile only calls two read-only endpoints confirmed by the
existing E2E setup: `GET /articles/random?limit=5` and `GET /tags`.
It does not create users, mutate data, or call third-party providers.

Install Locust in the Python environment:

```bash
python -m pip install locust
```

Start with a local backend:

```bash
locust -f tests/performance/locustfile.py --host http://127.0.0.1:8765
```

Or use an explicitly approved Azure staging URL:

```bash
locust -f tests/performance/locustfile.py --host https://YOUR-STAGING-HOST
```

Open the Locust UI at `http://localhost:8089`. Start conservatively:
- 1–2 users
- spawn rate 1 user/second
- 1–2 minutes
- then 5 users only if the first run is healthy

Do not run against production or increase users sharply without approval.
Because the Azure Container App scales to zero and may cold-start, record
cold-start latency separately from steady-state latency. Do not mix those
results into the steady-state percentile baseline.

### Metrics to record

For each run, save:
- target URL and deployment revision
- date/time and whether the app was cold or warm
- user count and spawn rate
- request count, failures, median, p95 and p99 latency
- CPU/memory/restarts from Azure metrics
- any 429, 5xx, timeout, or dependency errors

Export a CSV from the Locust UI after each run. Keep load tests manual and
out of the normal CI pipeline.
