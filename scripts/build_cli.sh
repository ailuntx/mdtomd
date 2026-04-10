#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m pip install --user build twine
rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist"
"$PYTHON_BIN" -m build --sdist --wheel "$ROOT_DIR"
"$PYTHON_BIN" -m twine check "$ROOT_DIR"/dist/*
