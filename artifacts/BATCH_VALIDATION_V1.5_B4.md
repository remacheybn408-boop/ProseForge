# V1.5 B4 Podman Batch

Tasks: V15-008/009. Packaging smoke and upgrade/rollback.

Command: podman run --rm ... pytest -q tests/packaging tests/operations tests/fault_injection
Result: exit 0; **5 passed**.

Linux source-runtime archive smoke passed in Podman. Native macOS signing and Windows installer execution remain not tested on this Windows host.
