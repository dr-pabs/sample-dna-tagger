#!/bin/bash
# ---------------------------------------------------------------------------
# sign-and-notarize.sh — Code-sign, package, and notarize Sample DNA Tagger
# for macOS distribution.
#
# Prerequisites:
#   - Apple Developer ID Application certificate installed in Keychain
#   - App-specific password stored in Keychain as "AC_PASSWORD"
#   - Xcode command-line tools installed
#
# Usage:
#   export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
#   ./sign-and-notarize.sh
#
# Output:
#   dist/Sample DNA Tagger.dmg
# ---------------------------------------------------------------------------
set -euo pipefail

APP_NAME="Sample DNA Tagger"
BUNDLE_ID="com.sampledna.tagger"
APP_PATH="dist/${APP_NAME}.app"
DMG_PATH="dist/${APP_NAME}.dmg"
ENTITLEMENTS="entitlements.plist"

# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------

CODESIGN_IDENTITY="${CODESIGN_IDENTITY:-}"
if [[ -z "$CODESIGN_IDENTITY" ]]; then
    echo "ERROR: Set CODESIGN_IDENTITY environment variable"
    echo "  export CODESIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'"
    exit 1
fi

# App-specific password from Keychain (create with:
#   xcrun notarytool store-credentials "AC_PASSWORD"
# )
KEYCHAIN_PROFILE="${KEYCHAIN_PROFILE:-AC_PASSWORD}"

# ---------------------------------------------------------------------------
# 1. Deep sign the app bundle
# ---------------------------------------------------------------------------

echo "=== Code-signing ${APP_NAME}.app ==="

# Sign all nested binaries and libraries first
codesign --force --options runtime \
    --sign "$CODESIGN_IDENTITY" \
    --entitlements "$ENTITLEMENTS" \
    --deep \
    "$APP_PATH"

# Verify signature
codesign --verify --verbose "$APP_PATH"
codesign --display --verbose=4 "$APP_PATH"

# ---------------------------------------------------------------------------
# 2. Create DMG
# ---------------------------------------------------------------------------

echo ""
echo "=== Creating DMG ==="

# Remove old DMG
rm -f "$DMG_PATH"

# Create a temporary directory for DMG contents
TMP_DMG=$(mktemp -d)
cp -R "$APP_PATH" "$TMP_DMG/"
ln -s /Applications "$TMP_DMG/Applications"

# Use create-dmg if available, otherwise hdiutil
if command -v create-dmg >/dev/null 2>&1; then
    create-dmg \
        --volname "$APP_NAME" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "$APP_NAME.app" 175 120 \
        --hide-extension "$APP_NAME.app" \
        --app-drop-link 425 120 \
        "$DMG_PATH" \
        "$TMP_DMG"
else
    # Fallback: simple DMG with hdiutil
    hdiutil create -srcfolder "$TMP_DMG" -volname "$APP_NAME" \
        -format UDZO -o "$DMG_PATH"
fi

rm -rf "$TMP_DMG"

# Sign the DMG
codesign --force --sign "$CODESIGN_IDENTITY" "$DMG_PATH"

# ---------------------------------------------------------------------------
# 3. Notarize
# ---------------------------------------------------------------------------

echo ""
echo "=== Notarizing DMG ==="

xcrun notarytool submit "$DMG_PATH" \
    --keychain-profile "$KEYCHAIN_PROFILE" \
    --wait

# ---------------------------------------------------------------------------
# 4. Staple
# ---------------------------------------------------------------------------

echo ""
echo "=== Stapling notarization ticket ==="

xcrun stapler staple "$DMG_PATH"
xcrun stapler staple "$APP_PATH"

# Verify
spctl -a -t open --context context:primary-signature -v "$DMG_PATH" || true

echo ""
echo "=== Done ==="
echo "Signed app: ${APP_PATH}"
echo "Signed DMG: ${DMG_PATH}"
