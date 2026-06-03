#!/usr/bin/env bash
# install.sh — Novel Forge installer (macOS / Linux)
# Make executable: chmod +x install.sh
set -e

# Unified Python detection: prefer venv, fall back to system
PYTHON=${PYTHON:-python3}
if [ -d ".venv" ]; then
  . .venv/bin/activate 2>/dev/null || true
  PYTHON=python
fi

echo "============================================"
VER=$(cat VERSION 2>/dev/null || echo "v0.6.5")
echo "  Novel Forge - 小说引擎 $VER"
echo "  Install (Mac / Linux)"
echo "============================================"
echo ""

# Detect OS for helpful messaging
OS_NAME=$(uname -s 2>/dev/null || echo "Unknown")
echo "[INFO] Detected OS: $OS_NAME"

if ! command -v $PYTHON >/dev/null 2>&1; then
  echo "[ERROR] $PYTHON not found. Please install Python 3.10+."
  echo ""
  echo "  macOS:   brew install python@3.11"
  echo "  Ubuntu:  sudo apt install python3 python3-venv python3-pip"
  echo "  Fedora:  sudo dnf install python3 python3-pip"
  echo "  Arch:    sudo pacman -S python python-pip"
  exit 1
fi

PYVER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[OK] Python $PYVER"

# Check minimum Python version
MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 8 ]; }; then
  echo "[ERROR] Python 3.8+ required, found $PYVER"
  exit 1
fi

# Create config from example if missing
if [ ! -f "config.json" ] && [ -f "config.example.json" ]; then
  cp config.example.json config.json
  echo "[OK] config.json created from config.example.json"
fi

# Create virtual environment
echo ""
echo "[STEP] Creating virtual environment..."
$PYTHON -m venv .venv
source .venv/bin/activate
PYTHON=python

# Upgrade pip
$PYTHON -m pip install --upgrade pip -q

# Install dependencies
if [ -f "requirements.txt" ]; then
  echo "[STEP] Installing dependencies..."
  pip install -r requirements.txt -q
  echo "[OK] Dependencies installed"
else
  echo "[WARN] requirements.txt not found — skipping pip install"
fi

# Initialize workspace
echo ""
echo "[STEP] Initializing workspace..."
$PYTHON novel.py db init 2>/dev/null || echo "[OK] Workspace may already be initialized"

# Run status check
echo ""
$PYTHON novel.py status

echo ""
echo "============================================"
echo "  Install complete."
echo ""
echo "  Quick start:"
echo "    source .venv/bin/activate"
echo "    python novel.py db list"
echo "    python novel.py demo"
echo ""
echo "  For help: python novel.py scc-help"
echo "============================================"
