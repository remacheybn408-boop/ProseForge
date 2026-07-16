from __future__ import annotations

from pathlib import Path


REQUIRED_JOBS = {
    "lint",
    "legacy-test",
    "api-unit",
    "api-integration",
    "frontend-unit",
    "frontend-build",
    "migration-test",
    "provider-contract",
    "docker-build",
    "e2e",
    "recovery-test",
    "security-scan",
}


def test_ci_defines_all_required_docker_gates():
    workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "docker compose -f compose.yaml -f compose.test.yaml" in workflow
    assert all(f"  {job}:" in workflow for job in REQUIRED_JOBS)
