# Build & Deployment Guide

> How to build, sign, and distribute Sample DNA Tagger on macOS and Windows.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Setup](#development-setup)
3. [Building Locally](#building-locally)
   - [macOS](#macos)
   - [Windows](#windows)
4. [Code Signing](#code-signing)
   - [macOS (Apple Developer ID)](#macos-apple-developer-id)
   - [Windows (Authenticode)](#windows-authenticode)
5. [Notarization (macOS)](#notarization-macos)
6. [GitHub Actions CI/CD](#github-actions-cicd)
7. [Release Process](#release-process)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### All Platforms

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| Git | any | Version control |

### macOS Only

| Tool | Version | Purpose |
|------|---------|---------|
| Xcode Command Line Tools | 15+ | `codesign`, `notarytool`, `stapler` |
| Apple Developer ID cert | active | Code signing |
| App-specific password | — | Notarization via Apple ID |

### Windows Only

| Tool | Version | Purpose |
|------|---------|---------|
| Visual C++ Build Tools | 2019+ | Native extension compilation |
| Windows SDK | 10+ | Optional — for advanced signing |
| Code signing certificate | active | `.pfx` from CA or self-signed |

---

## Development Setup

### 1. Clone the repo

```bash
git clone https://github.com/dr-pabs/sample-dna-tagger.git
cd sample-dna-tagger
```

### 2. Install Python dependencies

```bash
# Using uv (recommended)
uv venv --python 3.11
source .venv/bin/activate  # macOS/Linux
# or: .venv\Scripts\activate  # Windows
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install --cache .npm-cache
cd ..
```

### 4. Run in development mode

```bash
# Terminal 1 — backend
python launch.py --dev

# Terminal 2 — frontend (optional, launch.py --dev opens a window)
cd frontend
npm run dev
```

The app opens in a native desktop window. API calls proxy through Vite to the FastAPI backend.

---

## Building Locally

### macOS

#### Unsigned build (quick test)

```bash
chmod +x build-macos.sh
./build-macos.sh
```

**Output:** `dist/Sample DNA Tagger.app` (~280–300 MB)

**Test the build:**

```bash
open "dist/Sample DNA Tagger.app"
# Or headless:
# "dist/Sample DNA Tagger.app/Contents/MacOS/Sample DNA Tagger" --no-window
```

#### Signed + notarized build (for distribution)

See [Code Signing](#macos-apple-developer-id) and [Notarization](#notarization-macos) sections first, then run:

```bash
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
chmod +x build-macos.sh sign-and-notarize.sh
./build-macos.sh
./sign-and-notarize.sh
```

**Output:** `dist/Sample DNA Tagger.dmg`

---

### Windows

```batch
build-windows.bat
```

**Output:** `dist\Sample DNA Tagger\Sample DNA Tagger.exe` (~300–350 MB)

**Test the build:**

```batch
dist\Sample DNA Tagger\Sample DNA Tagger.exe
```

---

## Code Signing

### macOS (Apple Developer ID)

#### 1. Obtain a certificate

- Enroll in the [Apple Developer Program](https://developer.apple.com/programs/) ($99/year)
- Request a **Developer ID Application** certificate in Xcode → Preferences → Accounts
- Download and install it to your Keychain

#### 2. Verify the certificate

```bash
security find-identity -v -p codesigning
```

You should see something like:

```
  1) ABCDEF1234567890ABCDEF1234567890ABCDEF12 "Developer ID Application: Your Name (TEAMID)"
```

#### 3. Set the environment variable

```bash
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
```

The `build-macos.sh` script passes this to PyInstaller via the `.spec` file, which signs the `.app` bundle automatically.

#### 4. Manual signing (if needed)

```bash
codesign --force --options runtime \
  --sign "$CODESIGN_IDENTITY" \
  --entitlements entitlements.plist \
  --deep \
  "dist/Sample DNA Tagger.app"
```

---

### Windows (Authenticode)

#### 1. Obtain a certificate

Purchase a code signing certificate from a trusted CA (e.g., DigiCert, Sectigo, SSL.com) or create a self-signed cert for testing.

#### 2. Export as PFX

Include the private key and full certificate chain. Note the password.

#### 3. Sign the executable

```batch
signtool sign /f path\to\certificate.pfx /p PASSWORD ^
  /tr http://timestamp.digicert.com /td sha256 /fd sha256 ^
  "dist\Sample DNA Tagger\Sample DNA Tagger.exe"
```

**Verify:**

```batch
signtool verify /pa "dist\Sample DNA Tagger\Sample DNA Tagger.exe"
```

> ⚠️ **Note:** Unsigned Windows executables may trigger Microsoft Defender SmartScreen. An Extended Validation (EV) certificate provides immediate reputation; standard certificates build reputation over time.

---

## Notarization (macOS)

Apple requires notarization for apps distributed outside the App Store on macOS 10.15+.
n
### 1. Create an app-specific password

- Go to [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security → App-Specific Passwords
- Generate a password (e.g., "SampleDNANotary")
- Store it in your Keychain:

```bash
xcrun notarytool store-credentials "AC_PASSWORD" \
  --apple-id "your@email.com" \
  --team-id "TEAMID" \
  --password "abcd-efgh-ijkl-mnop"
```

### 2. Run the notarization script

```bash
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
./sign-and-notarize.sh
```

This script:
1. Deep-signs the `.app` bundle
2. Creates a DMG with the app and a symlink to `/Applications`
3. Signs the DMG
4. Submits the DMG to Apple for notarization
5. Waits for approval
6. Staples the notarization ticket to both the DMG and the `.app`

### 3. Verify notarization

```bash
spctl -a -t open --context context:primary-signature -v "dist/Sample DNA Tagger.dmg"
xcrun stapler validate "dist/Sample DNA Tagger.app"
```

---

## GitHub Actions CI/CD

The repo includes `.github/workflows/build.yml` which automates testing and building on every push and tag.

### Workflow Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Push to   │────▶│   Test on   │────▶│  Build + Upload │
│   main / v* │     │ 3 OS (matrix)│     │   (tags only)   │
└─────────────┘     └─────────────┘     └─────────────────┘
```

### Jobs

| Job | Runner | Trigger | Output |
|-----|--------|---------|--------|
| `test` | ubuntu, macOS, Windows | Every push & PR | — |
| `build-macos` | macos-latest | Tags (`v*`) | `Sample-DNA-Tagger-macOS` artifact |
| `build-windows` | windows-latest | Tags (`v*`) | `Sample-DNA-Tagger-Windows` artifact |

### Trigger a release build

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

GitHub Actions will:
1. Run the test suite on all 3 OSes
2. Build the `.app` on macOS and `.exe` on Windows
3. Upload artifacts to the workflow run

### Download artifacts

Go to **Actions** → select the workflow run → **Artifacts** section → download.

### Optional: Auto-create GitHub Release

Extend the workflow with a `release` job that creates a GitHub Release and attaches the artifacts:

```yaml
  release:
    needs: [build-macos, build-windows]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
      - uses: softprops/action-gh-release@v1
        with:
          files: |
            Sample-DNA-Tagger-macOS/**
            Sample-DNA-Tagger-Windows/**
```

---

## Release Process

### 1. Update version

```bash
# Update pyproject.toml version
# Update frontend/package.json version
# Update ARCHITECTURE.md version references
# Update adr/ if any new decisions were made
```

### 2. Update CHANGELOG.md

Follow [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [0.2.0] - 2026-05-26

### Added
- Real-time file-system watcher (ADR-005)
- Waveform PNG generation (ADR-006)
- Auto-update notifications (ADR-007)
- macOS code signing and notarization support
- GitHub Actions CI/CD

### Changed
- Settings API returns aggregated response
- Scan status shape aligned with frontend

### Fixed
- FastAPI `on_event` deprecation warning
- PyInstaller missing `sample_dna_tagger` modules
```

### 3. Commit and tag

```bash
git add -A
git commit -m "chore(release): v0.2.0"
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin main --tags
```

### 4. Wait for CI

GitHub Actions will build artifacts. Download and test them.

### 5. Sign and notarize (macOS)

```bash
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
./sign-and-notarize.sh
```

### 6. Create GitHub Release

- Go to **Releases** → **Draft a new release**
- Select the `v0.2.0` tag
- Upload `dist/Sample DNA Tagger.dmg` (macOS)
- Upload `dist/Sample DNA Tagger.zip` or folder (Windows)
- Paste CHANGELOG entry into release notes
- Publish

### 7. Verify

- Download the release asset on a clean machine
- Verify it opens without warnings
- Verify auto-updater detects the release (if this is not the latest)

---

## Troubleshooting

### macOS

#### "App is damaged and can't be opened"

**Cause:** Gatekeeper blocks unsigned or unnotarized apps.

**Fix:** Code sign and notarize. For local testing only:

```bash
xattr -cr "dist/Sample DNA Tagger.app"
```

#### "Sample DNA Tagger can't be opened because the developer cannot be verified"

**Cause:** The app is signed but not notarized, or the cert is not a Developer ID.

**Fix:** Ensure you're using a **Developer ID Application** certificate (not Mac Development or Mac App Distribution) and run notarization.

#### PyInstaller: `ModuleNotFoundError: No module named 'sample_dna_tagger'`

**Cause:** Hidden imports missing in `.spec`.

**Fix:** Ensure `SampleDNA.spec` includes all `sample_dna_tagger.*` submodules under `hiddenimports`. Already fixed in current version.

#### PyInstaller: `Hidden import 'pywebview.platforms.cocoa' not found`

**Cause:** Harmless warning. The platform-specific backend is loaded dynamically at runtime. The `.spec` includes it for safety.

---

### Windows

#### "Windows protected your PC" (SmartScreen)

**Cause:** The executable is unsigned or the certificate lacks reputation.

**Fix:**
- Short term: Click **More info** → **Run anyway**
- Long term: Sign with an EV code signing certificate for immediate reputation

#### `librosa` fails to load audio

**Cause:** `soundfile` requires the native `libsndfile` library, which may not be bundled correctly.

**Fix:** Ensure `soundfile` is in `hiddenimports` in `SampleDNA.spec`. If issues persist, include `soundfile.libs` data files in the spec.

#### Console window flashes briefly

**Cause:** `console=True` in PyInstaller spec or a subprocess spawning a shell.

**Fix:** The current spec sets `console=False`. Check `launch.py` does not spawn subprocesses with `shell=True`.

---

### General

#### Build size is too large (>400MB)

**Cause:** PyInstaller bundles all dependencies including heavy ones like `scipy`, `sklearn`, `numba`.

**Mitigation:**
- Use UPX compression (already enabled in spec)
- Audit `excludes` list in `SampleDNA.spec` for unused packages
- Consider `onedir` instead of `onefile` (already using `COLLECT`)

#### Frontend build fails with TypeScript errors

```bash
cd frontend
npm run build
```

**Fix:** Check for type mismatches between `api.ts` and backend Pydantic models. Run `npx tsc -b --noEmit` for diagnostics.

#### Database is locked during scan

**Cause:** Concurrent writes from scanner and watcher threads.

**Fix:** The DB layer uses `asyncio.Lock` for write serialization. If the issue persists, check that all DB access goes through the singleton connection, not independent `aiosqlite.connect()` calls.

---

## Quick Reference

### One-liners

```bash
# macOS unsigned build
./build-macos.sh

# macOS signed + notarized build
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
./build-macos.sh && ./sign-and-notarize.sh

# Windows build
build-windows.bat

# Run tests
pytest -v

# Type-check frontend
cd frontend && npx tsc -b --noEmit

# Clean everything
rm -rf dist build frontend/dist frontend/node_modules .pytest_cache
```

### File Checklist for Release

- [ ] `pyproject.toml` version bumped
- [ ] `frontend/package.json` version bumped
- [ ] `CHANGELOG.md` updated
- [ ] Tests pass (`pytest -v`)
- [ ] Frontend builds (`npm run build`)
- [ ] macOS `.app` builds and runs
- [ ] macOS `.app` is signed (`codesign -v`)
- [ ] macOS DMG is notarized (`spctl -a`)
- [ ] Windows `.exe` builds and runs
- [ ] Windows `.exe` is signed (`signtool verify`)
- [ ] GitHub Release drafted with artifacts
- [ ] Release notes include CHANGELOG

---

*Last updated: 2026-05-26*
