#!/usr/bin/env bash
# Run all frontend code-quality checks.
# Exit code 0 = all checks passed; non-zero = at least one check failed.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Checking frontend formatting (Prettier)..."
if ! npx prettier --check "frontend/**/*.{js,html,css}"; then
  echo ""
  echo "Formatting issues found. Run 'npm run format' to auto-fix."
  exit 1
fi

echo ""
echo "All frontend quality checks passed."
