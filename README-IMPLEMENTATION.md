# Applying the VNAANA code-quality configuration

This bundle contains configuration files based on the repository details
provided, including an updated GitHub Actions workflow.

## 1. Copy configuration files

Copy the contents of this bundle into the repository root, preserving paths.
Review the bundled `.github/workflows/ci.yml` before replacing your existing
workflow. It preserves the supplied test, publish, and deploy flow, adds a
separate static quality job, and makes publishing depend on both test jobs.

The `.importlinter` file corrects the DAL package casing to `Backend.Dal`,
matching the supplied directory listing.

## 2. Install frontend quality tools

From `Frontend/`, run:

```bash
npm install --save-dev prettier jscpd
```

Merge these scripts into the existing `scripts` object in `Frontend/package.json`
(preserve all existing scripts):

```json
{
  "format": "prettier --write \"src/**/*.{ts,tsx,css}\" \"*.{json,js,ts}\"",
  "format:check": "prettier --check \"src/**/*.{ts,tsx,css}\" \"*.{json,js,ts}\"",
  "duplication": "jscpd ../Backend src"
}
```

The install command updates `package.json` and `package-lock.json`. Commit both.
Do not replace the existing ESLint, typecheck, build, or test scripts.

## 3. Install Python development tools locally

In the repository's virtual environment:

```bash
python -m pip install ruff pytest-cov import-linter
```

These are development tools. They are deliberately not added to the production
runtime requirements in `requirements.txt`.

## 4. Apply the workflow

The bundled `.github/workflows/ci.yml`:
- Installs `pytest-cov` in the existing test job and measures Backend coverage
  during the existing pytest run (no duplicate test execution).
- Adds a `Code Quality` job that does not start Supabase or Playwright.
- Makes Docker publishing depend on both `test` and `code-quality`.
- Keeps deployment dependent on successful publishing.

The frontend package scripts and dependencies in step 2 must be committed before
the workflow can pass.

## 5. Validate incrementally

Run the checks locally and fix existing violations. A first run may identify
pre-existing formatting, lint, complexity, duplication, or coverage issues.
Review those findings rather than weakening the thresholds automatically.
