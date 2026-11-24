# CI integration: separate frontend-performance job

Add a standalone `frontend-performance` job alongside `code-quality`.
Do not make it depend on the backend integration-test job: CI jobs run on
separate machines, so it must start its own local Supabase/backend stack.

The job should:
1. Check out the repository.
2. Set up Python 3.12, Node 22 and pnpm 9.10.0.
3. Install backend requirements plus `pytest`, `pytest-cov`, `httpx`,
   `sqlalchemy`, and the PostgreSQL driver used by the E2E fixtures.
4. Install frontend dependencies and Playwright Chromium.
5. Start local Supabase using the same command as E2E.
6. Build the frontend with local Supabase/API environment values.
7. Create a deterministic logged-in storage state using the existing
   `ready_user` and `logged_in_state` fixtures.
8. Start the backend and production preview, run LHCI, then stop both.
9. Upload `.lighthouseci/` as an artifact even when assertions fail.

Important: the current `tests/e2e/conftest.py` `servers` fixture starts the
Vite development server and stops the API when its session ends. Do not
simply import that fixture into a separate job and assume it gives Lighthouse
a production preview plus a still-running API. Extract the local Supabase,
database-seeding, ready-user and server-start helpers into reusable fixtures,
or add a dedicated performance fixture that builds first and starts
`uvicorn` plus `vite preview` on the exact origin used by the saved auth state.

Keep this job separate from `publish` until its baseline is stable. Once
stable, add `frontend-performance` to `publish.needs`.
