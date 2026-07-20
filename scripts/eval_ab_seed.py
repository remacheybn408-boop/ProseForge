"""V3 评测 A/B 证据种子（L2 步骤）。

在同一项目里先后执行 run A（单 scene_writer 基线）与 run B
（scene_writer → continuity_reviewer → merge_editor 集群），随后调用
scripts/eval_ab_compare.py 输出脱敏聚合判定。仅面向测试栈
（provider-mock）；不输出正文内容，只输出 run id 与聚合分数。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("EVAL_BASE_URL", "http://api:8000")
EMAIL = os.environ.get("E2E_EMAIL", "v2-e2e-b074fc29@example.local")
PASSWORD = os.environ.get("E2E_PASSWORD", "E2ePassw0rd!")


def call(method: str, path: str, body: dict | None = None, token: str | None = None, key: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", f"Bearer {token}")
    if key:
        req.add_header("Idempotency-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read() or b"{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def wait_terminal(token: str, run_id: str, timeout_s: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status, run = call("GET", f"/api/v3/agent-runs/{run_id}", token=token)
        if status != 200:
            raise RuntimeError(f"get run {run_id}: {status} {run}")
        if run["status"] in {"COMPLETED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"}:
            return run
        time.sleep(1.0)
    raise TimeoutError(f"run {run_id} did not reach a terminal state in {timeout_s}s")


def main() -> int:
    stamp = uuid.uuid4().hex[:8]
    call("POST", "/api/v1/auth/setup", {"email": EMAIL, "password": PASSWORD})  # 201 或 409 均可
    status, login = call("POST", "/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
    if status != 200:
        raise RuntimeError(f"login: {status} {login}")
    token = login["access_token"]
    call("POST", "/api/v1/credentials", {"provider": "openai", "api_key": "mock-api-key", "base_url": "http://provider-mock:8080/v1", "allow_local": True}, token=token)

    status, project = call("POST", "/api/v1/projects", {"title": f"V3 eval {stamp}", "slug": f"v3-eval-{stamp}"}, token=token)
    if status != 201:
        raise RuntimeError(f"create project: {status} {project}")
    project_id = project["id"]

    def start_run(goal: str, tasks: list[dict], key: str) -> str:
        status, run = call(
            "POST", f"/api/v3/projects/{project_id}/agent-runs",
            {"goal": goal, "tasks": tasks, "budget_limit": 1000},
            token=token, key=key,
        )
        if status != 201:
            raise RuntimeError(f"start run: {status} {run}")
        return run["id"]

    run_a = start_run(
        "Baseline single writer for the evaluation harness.",
        [{"id": "write", "role": "scene_writer", "token_budget": 200}],
        f"eval-a-{stamp}",
    )
    final_a = wait_terminal(token, run_a)
    run_b = start_run(
        "Swarm writer with independent review and merge for the evaluation harness.",
        [
            {"id": "write", "role": "scene_writer", "token_budget": 200},
            {"id": "review", "role": "continuity_reviewer", "depends_on": ["write"], "token_budget": 200},
            {"id": "merge", "role": "merge_editor", "depends_on": ["review"], "token_budget": 200},
        ],
        f"eval-b-{stamp}",
    )
    final_b = wait_terminal(token, run_b)
    print(f"run A {run_a} -> {final_a['status']} (budget_used={final_a.get('budget_used')})")
    print(f"run B {run_b} -> {final_b['status']} (budget_used={final_b.get('budget_used')})")
    if final_a["status"] != "COMPLETED" or final_b["status"] != "COMPLETED":
        return 1

    result = subprocess.run(
        [sys.executable, "scripts/eval_ab_compare.py", "--run-a", run_a, "--run-b", run_b],
        capture_output=True, text=True, timeout=120,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
