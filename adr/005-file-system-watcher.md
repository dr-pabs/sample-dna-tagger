# ADR-005: File-System Watcher (watchdog)

## Status
Accepted

## Context
Users expect new samples that land in their watch folders to appear in the library immediately, without manually triggering a rescan. The existing scan model requires the user to press "Scan all now" or add a new root.

## Decision
Integrate `watchdog` to monitor all configured scan roots recursively. File creation and modification events are debounced (2s) and trigger a background rescan of the affected root. File deletion events remove the sample from the database immediately.

## Consequences

- **Positive**: Real-time sample discovery; deleted files are cleaned up automatically.
- **Positive**: De-bounced rescans batch rapid file events (e.g., copying a pack) into a single scan.
- **Negative**: Adds a background thread per watched root; large trees may consume OS file-descriptor budget.
- **Trade-off**: `watchdog` uses `FSEvents` on macOS, `ReadDirectoryChangesW` on Windows, and `inotify` on Linux — no custom kernel code needed.
