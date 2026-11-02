# Ask Nova team testing guide

> **Thursday demo branch only:** `demo/ask-nova-thursday` combines the latest reviewed frontend/DAL baseline with the published AI backend and Ask Nova improvements. Do not merge it directly into `dev`; coordinate the final integration with the owners of `Frontend-dev`, `Database-dev`, `Backend-AI-service`, and `dev`.

This branch connects the database-backed news feed to the existing Ask Nova interface. It sends the selected article context to FastAPI (`/ai/ask` or `/ai/summarize`), which uses the local Ollama `llama3.2` model. It supports full-article grounding and a clearly labelled preview-only mode when the database article has no scraped content.

## 1. Prerequisites

- Windows PowerShell.
- Git.
- **Python 3.12.2** (the version used by CI). The project does not declare a formal minimum Python version.
- **Node.js 22 or newer.** The locked `@supabase/supabase-js` package requires Node 22+. Node 22.23.4 with npm 10.8.3 has been verified locally.
- Ollama for Windows. Install it from <https://ollama.com/download/windows> if it is not already installed.
- Access to the team's Supabase PostgreSQL database and Supabase project configuration.
- A Google account accepted by the team's Supabase Google provider if authentication is being tested.

Use a separate clone so the shared `dev` checkout is not changed:

```powershell
git clone --single-branch --branch demo/ask-nova-thursday `
  https://github.com/RikH2023/VNAANA.git `
  D:\VNAANA-AskNova-Review
Set-Location -LiteralPath 'D:\VNAANA-AskNova-Review'
```

Run all backend commands from the repository root, not from inside `Backend`.

## 2. Obtain configuration securely

Ask the database/Supabase owner for these values through the team's approved private channel:

- Supabase PostgreSQL `DATABASE_URL` with a URL-encoded password and `sslmode=require`.
- Supabase project URL.
- Supabase publishable/anonymous key. Do not use a service-role key in the frontend.

Do not paste secrets into GitHub issues, commits, screenshots, terminal transcripts, or chat messages. The two environment files below are ignored by Git, but check `git status` before committing anything.

### Backend environment

Create `Backend/.env` (not a root `.env`) using placeholders first:

```ini
DATABASE_URL="postgresql+psycopg://<user>:<URL-encoded-password>@<pooler-host>:5432/<database>?sslmode=require"
SQL_ECHO=false
SUPABASE_URL="https://<project-reference>.supabase.co"
SUPABASE_PUBLISHABLE_KEY="<team-provided-publishable-key>"
```

Replace the placeholders locally with team-provided values. `Backend/config.py` and Alembic both load `Backend/.env`.

The AI defaults in `Backend/config.py` already match the demo and may also be overridden in `Backend/.env` if the team needs a different local value:

- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `OLLAMA_MODEL=llama3.2`
- `OLLAMA_TIMEOUT_SECONDS=90`

No override is needed for the defaults. If required, set them only in `Backend/.env` or in the backend terminal before startup:

```powershell
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODEL = 'llama3.2'
$env:OLLAMA_TIMEOUT_SECONDS = '90'
```

### Frontend environment

Create `Frontend/.env.local`:

```ini
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://<project-reference>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<team-provided-publishable-key>
```

The Supabase URL/key are required when the frontend module starts, even if login is not being tested. The API URL is required for both `/articles/random` and Ask Nova requests.

## 3. Install backend dependencies

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe -c "import fastapi, sqlalchemy, alembic, psycopg, httpx; print('Backend imports OK')"
```

Do not run provider seeding, news gathering, or other database-writing utilities for this test.

## 4. Check database migration status (read-only)

The repository's expected Alembic head on this branch is `c91e4a72b608`, which revises `fdf3a95033c6` and seeds the default tag names.

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini heads
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini current
```

`heads` should report `c91e4a72b608`. `current` reports the shared database revision, which may still differ. Confirm that state with Hanh before the demo. These commands inspect revision state; they do not apply migrations. Do not run `alembic upgrade`, create migrations, seed tags/providers, or gather news independently.

The real feed requires the shared database to be reachable and to already contain article records. Some records have full scraped `content`; others contain only a headline and description.

## 5. Install frontend dependencies

```powershell
Set-Location -LiteralPath 'D:\VNAANA-AskNova-Review\Frontend'
node --version
npm --version
npm ci
npm run typecheck
```

Use `npm ci`, because the repository contains `package-lock.json`. Do not commit `node_modules` or `dist`.

## 6. Start Ollama

Open a separate PowerShell window:

```powershell
ollama --version
ollama list
```

If `llama3.2` is not listed, download it once:

```powershell
ollama pull llama3.2
```

Ollama's Windows application normally starts its local service automatically. If `http://127.0.0.1:11434` is not reachable, start it in that terminal:

```powershell
ollama serve
```

Keep it running. The model is approximately 2 GB and generation is CPU/RAM intensive.

## 7. Start FastAPI

Open another PowerShell window:

```powershell
Set-Location -LiteralPath 'D:\VNAANA-AskNova-Review'
.\.venv\Scripts\python.exe -m uvicorn Backend.main:app --reload --host 127.0.0.1 --port 8000
```

Check:

- API documentation: <http://localhost:8000/docs>
- Random feed endpoint: <http://localhost:8000/articles/random?limit=3>
- Ollama API used by FastAPI: `http://127.0.0.1:11434`

Keep the backend terminal open. Do not post article text, questions, or secret environment values when sharing logs.

### Why the local backend is required

The currently deployed Azure API does not contain this combined Ask Nova implementation and cannot access the Ollama server running on a teammate's laptop. For this demo, keep `VITE_API_BASE_URL=http://localhost:8000` so both the real news feed and Ask Nova use this branch's local FastAPI process. Do not point the frontend at the Azure URL and expect `/ai/ask` or `/ai/summarize` to use local Ollama.

## 8. Start Vite

Open another PowerShell window:

```powershell
Set-Location -LiteralPath 'D:\VNAANA-AskNova-Review\Frontend'
npm run dev
```

Open <http://localhost:5173>. The backend CORS configuration expects this exact origin and the Vite configuration uses port 5173 with `strictPort` enabled.

## 9. Test the complete flow

The expected path is:

`Supabase PostgreSQL -> GET /articles/random -> news feed -> Ask Nova -> POST /ai/ask or /ai/summarize -> Ollama llama3.2`

For each test, open the post's **Read more / Ask Nova** carousel section.

### Full-article post

1. Find a post where Nova says it is using the original article.
2. Ask a factual question clearly supported by that article.
3. Ask a question not answered by the article; expect `Not answered from this article` and `insufficient_information` wording.
4. Select English and Dutch separately. The answer language should follow the selector while evidence remains grounded in the original article.
5. Try **Explain it simpler**; this uses `/ai/summarize`, not factual Q&A.

### Preview-only post

1. Find a post showing that full article text is unavailable.
2. Confirm Nova states whether it is using the headline only or headline plus description.
3. Ask a question supported by that preview.
4. Ask for a detail absent from the preview; Nova should return insufficient information rather than imply it read the full article.

### Context separation

1. Ask a question on one post.
2. Move to another post and ask about a fact unique to the first post.
3. Nova should use the second post's context and refuse unsupported information.

The feed returns three random articles, so refresh if the first sample does not contain both grounding modes.

## 10. Authentication notes

- The frontend needs valid Supabase project configuration during startup.
- Google OAuth is the connected sign-in method. Email/password login currently displays a design-preview message and does not authenticate.
- Google redirect URL `http://localhost:5173/` must be allowed in the team's Supabase authentication configuration.
- After Google sign-in, the frontend calls `POST /users/me/bootstrap`; the backend verifies the Supabase token and creates or retrieves the application profile.
- A manually pre-created application user should not be necessary, but the Google account must be allowed by the team's Supabase project/provider settings.
- The news feed itself is currently rendered without requiring a signed-in session, but valid Supabase frontend configuration is still required for application initialization.

## 11. Common problems

| Symptom | Check |
|---|---|
| `Missing Supabase frontend configuration` | Confirm all three `VITE_*` names exist in `Frontend/.env.local`, then restart Vite. |
| `Missing API URL` | Set `VITE_API_BASE_URL=http://localhost:8000` and restart Vite. |
| Backend validation error for Supabase settings | Add `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` to `Backend/.env`. |
| Database connection/authentication error | Confirm the team-provided URL, URL-encoded password, pooler host, port and `sslmode=require`. Do not print the URL. |
| Alembic revision differs | Stop and contact the DAL owner; do not apply migrations independently. |
| Feed says it cannot load news | Check FastAPI, `DATABASE_URL`, `/articles/random?limit=3`, and `VITE_API_BASE_URL`. |
| AI returns HTTP 503 | Check that Ollama is running and `llama3.2` appears in `ollama list`. |
| AI returns HTTP 422 | The question may be blank/over 500 characters, or article context may exceed 12,000 characters. Long articles are not silently truncated. |
| Ask Nova is unavailable | The selected article may exceed the 12,000-character limit or have no usable grounding text. |
| Google sign-in does not return | Confirm the Supabase Google provider and `http://localhost:5173/` redirect URL with the team. |
| Port 5173 is occupied | Stop the other process. Vite uses `strictPort` and the backend only allows `http://localhost:5173`. |
| Response is slow | Local generation commonly takes several seconds and can approach the 90-second timeout on weaker laptops. Keep requests short and run one at a time. |

## 12. Known limitations

- This is a temporary testing branch with divergent frontend/DAL and `dev` history.
- `llama3.2` can still produce inconsistent wording. Dutch answers are experimental and should be checked carefully.
- Ask Nova uses one supplied article or preview, not independent multi-source verification.
- A returned source URL is the submitted article URL, not proof that Nova fetched or verified it.
- Preview-only answers are limited to the headline and available description.
- Simplification is prompt-grounded but does not use the exact-evidence validation used by factual Q&A.
- Articles above 12,000 characters are disabled instead of truncated.
- The feed is random, so the exact articles shown vary between refreshes.
- Email/password authentication is not implemented; only the Google OAuth path is connected.

When testing is complete, share reproducible errors without secrets, database URLs, complete private article text, or user access tokens. Coordinate the eventual integration with the owners of `dev`, `Frontend-dev`/`Database-dev`, and `Backend-AI-service`.
