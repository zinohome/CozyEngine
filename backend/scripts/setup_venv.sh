#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${BACKEND_DIR}/venv"

INSTALL_MODE="dev"  # dev | prod

usage() {
  cat <<EOF
Usage: $(basename "$0") [--prod]

Creates backend/venv (if missing) and installs Python deps.

  --prod   Install only runtime deps (pip install -e .)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--prod" ]]; then
  INSTALL_MODE="prod"
fi

if [[ ! -f "${BACKEND_DIR}/pyproject.toml" && ! -f "${BACKEND_DIR}/requirements.txt" ]]; then
  echo "ERROR: Not a Python backend project (missing pyproject.toml/requirements.txt) in: ${BACKEND_DIR}" >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating venv at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

PY="${VENV_DIR}/bin/python"

"${PY}" -m pip install --upgrade pip setuptools wheel

if [[ -f "${BACKEND_DIR}/pyproject.toml" ]]; then
  pushd "${BACKEND_DIR}" >/dev/null
  if [[ "${INSTALL_MODE}" == "dev" ]]; then
    echo "Installing deps: -e .[dev]"
    "${PY}" -m pip install -e ".[dev]"
  else
    echo "Installing deps: -e ."
    "${PY}" -m pip install -e .
  fi
  popd >/dev/null
elif [[ -f "${BACKEND_DIR}/requirements.txt" ]]; then
  pushd "${BACKEND_DIR}" >/dev/null
  echo "Installing deps: -r requirements.txt"
  "${PY}" -m pip install -r requirements.txt
  popd >/dev/null
fi

echo "OK: venv ready at ${VENV_DIR}"
