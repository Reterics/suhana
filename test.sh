#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR=".venv-ci"
REQ_FILE="requirements-ci.txt"

echo "Setting up CI virtual environment: ${VENV_DIR}"

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing dependencies from $REQ_FILE ..."
pip install --upgrade pip wheel setuptools
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r "$REQ_FILE"

echo "Running tests..."
python -m pytest --disable-warnings --cov=engine --cov-report=term

echo "All tests completed successfully."
