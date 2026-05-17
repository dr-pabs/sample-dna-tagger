#!/bin/bash
# ---------------------------------------------------------------------------
# build-macos.sh — Package Sample DNA Tagger as a macOS .app bundle.
#
# Prerequisites:
#   - Python 3.11+ with `pyinstaller` installed (pip install pyinstaller)
#   - Node.js 18+
#   - Project dependencies installed (pip install -e ".[dev]")
#
# Output:  dist/Sample DNA Tagger.app
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"

echo "=== Building frontend ==="
cd frontend && npm run build && cd ..

echo ""
echo "=== Cleaning previous builds ==="
rm -rf dist build

echo ""
echo "=== Running PyInstaller ==="
pyinstaller SampleDNA.spec --clean --noconfirm

echo ""
echo "=== Build complete ==="
echo "App bundle: dist/Sample DNA Tagger.app"
echo "Package size: $(du -sh dist/Sample\ DNA\ Tagger.app 2>/dev/null | cut -f1 || echo 'unknown')"
