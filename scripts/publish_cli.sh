#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REPOSITORY_URL="${TWINE_REPOSITORY_URL:-https://upload.pypi.org/legacy/}"

if [ ! -d "$ROOT_DIR/dist" ]; then
  echo "dist 不存在，请先执行 ./scripts/build_cli.sh" >&2
  exit 1
fi

: "${TWINE_PASSWORD:?请先设置 TWINE_PASSWORD 为 PyPI API token}"
export TWINE_USERNAME="${TWINE_USERNAME:-__token__}"
export TWINE_NON_INTERACTIVE=1

"$PYTHON_BIN" -m twine upload --repository-url "$REPOSITORY_URL" "$ROOT_DIR"/dist/*
