#!/bin/bash
# =============================================================================
# deploy.sh — Full CI/CD pipeline for Sample DNA Tagger
#
# Usage:
#   ./deploy.sh              # test + build (local)
#   ./deploy.sh --release    # test + build + create GitHub release
#   ./deploy.sh --test-only  # run tests only
#
# Prerequisites:
#   - Python 3.11+ with venv
#   - Node.js 18+
#   - (--release) GitHub CLI (`gh`) authenticated
# =============================================================================
set -euo pipefail

RELEASE=false
TEST_ONLY=false
VERSION=$(python3 -c "import runpy; print(runpy.run_path('sample_dna_tagger/__init__.py')['__version__'])")

# ── Parse args ────────────────────────────────────────────────────────

for arg in "$@"; do
    case $arg in
        --release)  RELEASE=true ;;
        --test-only) TEST_ONLY=true ;;
        *) echo "Unknown: $arg"; exit 1 ;;
    esac
done

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "━━━ Sample DNA Tagger v${VERSION} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Python environment ─────────────────────────────────────────────

echo ""
echo "▶ Setting up Python environment"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -e ".[dev]" -q

# ── 2. Lint ───────────────────────────────────────────────────────────

echo ""
echo "▶ Linting (ruff)"
ruff check sample_dna_tagger/ --output-format=concise || true

# ── 3. Test ───────────────────────────────────────────────────────────

echo ""
echo "▶ Running tests"
python -m pytest tests/ -v --tb=short --cov=sample_dna_tagger --cov-report=term

if [ "$TEST_ONLY" = true ]; then
    echo ""
    echo "✓ Tests complete (--test-only)"
    exit 0
fi

# ── 4. Build frontend ─────────────────────────────────────────────────

echo ""
echo "▶ Building frontend"
cd frontend
npm ci --cache .npm-cache --prefer-offline --silent 2>/dev/null || npm install --cache .npm-cache --silent
npm run build
cd ..

# ── 5. Build backend (platform-aware) ─────────────────────────────────

echo ""
echo "▶ Building backend binary"
pyinstaller SampleDNA.spec --clean --noconfirm

# ── 6. Verify output ──────────────────────────────────────────────────

if [ "$(uname)" = "Darwin" ]; then
    ARTIFACT="dist/Sample DNA Tagger.app"
    echo ""
    echo "✓ App bundle: $ARTIFACT"
    echo "  Size: $(du -sh "$ARTIFACT" 2>/dev/null | cut -f1)"
else
    ARTIFACT="dist/Sample DNA Tagger"
    echo ""
    echo "✓ Executable: $ARTIFACT/Sample DNA Tagger.exe"
    echo "  Size: $(du -sh "$ARTIFACT" 2>/dev/null | cut -f1)"
fi

# ── 7. GitHub release (--release only) ────────────────────────────────

if [ "$RELEASE" = true ]; then
    echo ""
    echo "▶ Creating GitHub release v${VERSION}"

    # Ensure we're on main and clean
    if [ -n "$(git status --porcelain)" ]; then
        echo "ERROR: Working tree is dirty. Commit or stash changes first."
        exit 1
    fi

    # Tag and push
    git tag -a "v${VERSION}" -m "Release v${VERSION}"
    git push origin "v${VERSION}"

    # Package artifact
    if [ "$(uname)" = "Darwin" ]; then
        PACKAGE="sample-dna-tagger-${VERSION}-macos.zip"
        cd dist
        ditto -c -k --keepParent "Sample DNA Tagger.app" "$PACKAGE"
        cd ..
        ARTIFACT_PATH="dist/$PACKAGE"
    else
        PACKAGE="sample-dna-tagger-${VERSION}-windows.zip"
        cd dist
        powershell -Command "Compress-Archive -Path 'Sample DNA Tagger/*' -DestinationPath '$PACKAGE'"
        cd ..
        ARTIFACT_PATH="dist/$PACKAGE"
    fi

    # Create GitHub release
    gh release create "v${VERSION}" \
        "$ARTIFACT_PATH" \
        --title "v${VERSION}" \
        --notes "Release v${VERSION}

See [CHANGELOG.md](CHANGELOG.md) for details."

    echo ""
    echo "✓ Release created: https://github.com/dr-pabs/sample-dna-tagger/releases/tag/v${VERSION}"
fi

echo ""
echo "━━━ Done ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
