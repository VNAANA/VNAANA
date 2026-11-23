
#!/usr/bin/env bash
set -e

echo "=== Python lint ==="
python -m ruff check Backend

echo "=== Python formatting ==="
python -m ruff format --check Backend

echo "=== Architecture checks ==="
lint-imports

echo "=== Frontend ESLint ==="
npm --prefix Frontend run lint

echo "=== Frontend type checking ==="
npm --prefix Frontend run typecheck

echo "=== Frontend formatting ==="
npm --prefix Frontend run format:check

echo "=== Duplication checks ==="
npm --prefix Frontend run duplication

echo "=== All quality checks passed! ==="
