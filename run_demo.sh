#!/usr/bin/env bash
set -e

# Unified Python detection: prefer venv, fall back to system
PYTHON=${PYTHON:-python3}
if [ -d ".venv" ]; then
  . .venv/bin/activate 2>/dev/null || true
  PYTHON=python
fi

echo "Running demo..."
$PYTHON novel.py demo
$PYTHON novel.py report

echo ""
echo "Demo complete. Open reports/index.html"
