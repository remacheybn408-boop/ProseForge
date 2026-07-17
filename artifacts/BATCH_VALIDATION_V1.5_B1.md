# V1.5 B1 Podman Batch

Tasks: V15-000/001/002. Runtime profile, platform paths, bootstrap and lifecycle.

Command: podman run --rm ... pytest -q tests/runtime
Result: exit 0; **40 passed, 1 warning**.

All Python execution was inside the Podman test container. No host Python test was used.
