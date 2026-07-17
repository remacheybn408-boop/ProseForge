# V1.5 B2 Podman Batch

Tasks: V15-003/004/005. SQLite/WAL, local queue, scheduler and migration recovery.

Command: podman run --rm ... pytest -q tests/database tests/tasks tests/migration
Result: exit 0; **27 passed**.

All Python execution was inside the Podman test container.
