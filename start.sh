#!/usr/bin/env bash
set -euo pipefail

SKIP_INSTALL=0
MODE="web"
PORT="18080"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./start.sh [--skip-install] [--mode web|gui] [--port 18080]

Options:
  --skip-install    Skip dependency installation
  --mode MODE       Launch mode: web or gui (default: web)
  --port PORT       Web port when mode=web (default: 18080)
EOF
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "$MODE" != "web" && "$MODE" != "gui" ]]; then
  echo "ERROR: --mode must be 'web' or 'gui'" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$SCRIPT_DIR"

step() { printf '\n==> %s\n' "$1"; }
ok() { printf 'OK: %s\n' "$1"; }
warn() { printf 'WARN: %s\n' "$1"; }
err() { printf 'ERROR: %s\n' "$1" >&2; }

step "Switch to project root"
cd "$PROJECT_ROOT"
ok "ProjectRoot = $PROJECT_ROOT"

step "Check Python"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
else
  err "Python not found. Install Python 3.10+ first."
  exit 1
fi

PYTHON_VER="$("$PYTHON_CMD" -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")"
ok "Python $PYTHON_VER"

# The tracked .venv in this repo is a Windows virtualenv. On Linux/macOS we keep
# a separate local environment to avoid rewriting those tracked files.
VENV_DIR=".venv-linux"
VENV_PYTHON="$PROJECT_ROOT/$VENV_DIR/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  step "Create virtual environment ($VENV_DIR)"
  "$PYTHON_CMD" -m venv "$VENV_DIR"
  ok "Virtual environment created"
else
  ok "Virtual environment already exists"
fi

if [[ $SKIP_INSTALL -eq 0 ]]; then
  step "Install or update dependencies"
  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -r requirements.txt
  "$VENV_PYTHON" -m patchright install chromium
  "$VENV_PYTHON" -m pip install -e .
  ok "Dependencies ready"
else
  warn "Skipped dependency installation (--skip-install)"
  if ! "$VENV_PYTHON" -c "import customtkinter, patchright, httpx, fastapi, uvicorn" >/dev/null 2>&1; then
    err "Dependencies are missing in $VENV_DIR. Run ./start.sh once without --skip-install."
    exit 1
  fi
fi

export PYTHONPATH="$PROJECT_ROOT/src"

step "Launch AutoRegister"
if [[ "$MODE" == "web" ]]; then
  ok "Web UI: http://127.0.0.1:$PORT"
  echo "$VENV_PYTHON -m auto_register --mode web --host 0.0.0.0 --port $PORT"
  exec "$VENV_PYTHON" -m auto_register --mode web --host 0.0.0.0 --port "$PORT"
fi

echo "$VENV_PYTHON -m auto_register --mode gui"
exec "$VENV_PYTHON" -m auto_register --mode gui
