#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Execution Receipt Verifier — v1.0

Checks that an execution_receipt.json is complete and valid.
All checks must pass, otherwise FAILED_EXECUTION_RECEIPT.

用法：
python scripts/verify_execution_receipt.py path/to/execution_receipt.json
"""

import json
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"FAILED_EXECUTION_RECEIPT: {message}")
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python scripts/verify_execution_receipt.py path/to/execution_receipt.json")

    receipt_path = Path(sys.argv[1])
    if not receipt_path.exists():
        fail(f"receipt file not found: {receipt_path}")

    try:
        d = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json: {exc}")

    # 1. commands_run is non-empty
    commands_run = d.get("commands_run", [])
    if not commands_run:
        fail("commands_run is empty")
    if not isinstance(commands_run, list):
        fail("commands_run is not a list")

    # 2. Each command has cmd, exit_code, timestamp
    required_cmd_fields = {"cmd", "exit_code", "timestamp"}
    for i, cmd in enumerate(commands_run):
        missing = required_cmd_fields - set(cmd.keys())
        if missing:
            fail(f"command[{i}] missing fields: {', '.join(sorted(missing))}")

    # 3. Key commands have exit_code == 0
    key_commands = [c for c in commands_run if c.get("is_key_command", False)]
    for cmd in key_commands:
        if int(cmd.get("exit_code", -1)) != 0:
            fail(f"key command '{cmd.get('cmd', 'unknown')}' has non-zero exit_code: {cmd.get('exit_code')}")

    # 4. run_report_path exists on disk
    run_report_path = d.get("run_report_path", "")
    if not run_report_path:
        fail("run_report_path is missing or empty")
    if not Path(run_report_path).exists():
        fail(f"run_report_path does not exist on disk: {run_report_path}")

    # 5. guard_result == "PASS_NOVEL_WRITE_GUARD"
    guard_result = d.get("guard_result", "")
    if guard_result != "PASS_NOVEL_WRITE_GUARD":
        fail(f"guard_result is '{guard_result}', expected 'PASS_NOVEL_WRITE_GUARD'")

    # 6. files_created_or_updated is non-empty
    files_created = d.get("files_created_or_updated", [])
    if not files_created:
        fail("files_created_or_updated is empty")
    if not isinstance(files_created, list):
        fail("files_created_or_updated is not a list")

    # 7. git_status_recorded == true
    if d.get("git_status_recorded") is not True:
        fail("git_status_recorded must be true")

    # 8. next_action is non-empty
    next_action = d.get("next_action", "")
    if not next_action:
        fail("next_action is empty or missing")

    print("PASS_EXECUTION_RECEIPT")


if __name__ == "__main__":
    main()
