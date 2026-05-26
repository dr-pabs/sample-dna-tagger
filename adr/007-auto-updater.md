# ADR-007: Auto-Updater (GitHub Releases API)

## Status
Accepted

## Context
Desktop apps distributed outside the Mac App Store need a mechanism to notify users when a new version is available. Full automatic updates (Sparkle, Squirrel) require significant infrastructure. For v0.1.x, a lightweight notification is sufficient.

## Decision
The frontend fetches the latest GitHub release via the public API on app startup. If `remote.tag_name > local.version`, a dismissible banner is shown with a download link. The backend exposes `GET /api/version` so the frontend always knows the current app version.

## Consequences

- **Positive**: Zero backend infrastructure; uses GitHub's free API.
- **Positive**: No auto-download or restart logic — keeps the app simple.
- **Negative**: User must manually download and replace the app.
- **Trade-off**: Sparkle (macOS) or Squirrel (Windows) can be added later for fully automatic updates.
