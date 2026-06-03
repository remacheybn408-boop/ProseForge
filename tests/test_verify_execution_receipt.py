"""
test_verify_execution_receipt.py — Execution Receipt Verifier 测试
"""
import pytest
import json
import tempfile
import sys
import os
import subprocess
from pathlib import Path

VERIFY_SCRIPT = Path(__file__).parent.parent / "scripts" / "verify_execution_receipt.py"


def _run_verify(receipt_dict):
    """Write receipt to temp file, run verifier, return (exit_code, stdout)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(receipt_dict, f)
        tmp = f.name
    result = subprocess.run([sys.executable, str(VERIFY_SCRIPT), tmp], capture_output=True, text=True, timeout=15)
    Path(tmp).unlink()
    return result.returncode, result.stdout


def _valid_receipt(**overrides):
    """Base valid receipt that should PASS."""
    # Create a temporary file to use as run_report_path
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({"status": "ok"}, f)
        report_tmp = f.name

    base = {
        "commands_run": [
            {"cmd": "python chapter_pipeline.py", "exit_code": 0, "timestamp": "2025-01-01T00:00:00Z", "is_key_command": True},
            {"cmd": "python agent_run_guard.py", "exit_code": 0, "timestamp": "2025-01-01T00:01:00Z", "is_key_command": True},
        ],
        "run_report_path": report_tmp,
        "guard_result": "PASS_NOVEL_WRITE_GUARD",
        "files_created_or_updated": ["chapter_001.txt", "chapter_run_report.json"],
        "git_status_recorded": True,
        "next_action": "write chapter 2"
    }
    base.update(overrides)
    return base, report_tmp


class TestVerifyPass:
    def test_complete_valid_receipt_passes(self):
        receipt, report_tmp = _valid_receipt()
        try:
            rc, out = _run_verify(receipt)
            assert rc == 0
            assert "PASS_EXECUTION_RECEIPT" in out
        finally:
            Path(report_tmp).unlink(missing_ok=True)


class TestVerifyFail:
    def test_empty_commands_run_fails(self):
        receipt, report_tmp = _valid_receipt(commands_run=[])
        try:
            rc, out = _run_verify(receipt)
            assert rc != 0
            assert "FAILED_EXECUTION_RECEIPT" in out
        finally:
            Path(report_tmp).unlink(missing_ok=True)

    def test_missing_exit_code_fails(self):
        receipt, report_tmp = _valid_receipt(
            commands_run=[{"cmd": "test", "timestamp": "2025-01-01T00:00:00Z"}]
        )
        try:
            rc, out = _run_verify(receipt)
            assert rc != 0
            assert "FAILED_EXECUTION_RECEIPT" in out
        finally:
            Path(report_tmp).unlink(missing_ok=True)

    def test_missing_run_report_path_fails(self):
        receipt, report_tmp = _valid_receipt(run_report_path="")
        try:
            rc, out = _run_verify(receipt)
            assert rc != 0
            assert "FAILED_EXECUTION_RECEIPT" in out
        finally:
            Path(report_tmp).unlink(missing_ok=True)

    def test_guard_result_not_pass_fails(self):
        receipt, report_tmp = _valid_receipt(guard_result="FAILED_NOVEL_WRITE_GUARD")
        try:
            rc, out = _run_verify(receipt)
            assert rc != 0
            assert "FAILED_EXECUTION_RECEIPT" in out
        finally:
            Path(report_tmp).unlink(missing_ok=True)

    def test_empty_files_created_or_updated_fails(self):
        receipt, report_tmp = _valid_receipt(files_created_or_updated=[])
        try:
            rc, out = _run_verify(receipt)
            assert rc != 0
            assert "FAILED_EXECUTION_RECEIPT" in out
        finally:
            Path(report_tmp).unlink(missing_ok=True)

    def test_missing_next_action_fails(self):
        receipt, report_tmp = _valid_receipt(next_action="")
        try:
            rc, out = _run_verify(receipt)
            assert rc != 0
            assert "FAILED_EXECUTION_RECEIPT" in out
        finally:
            Path(report_tmp).unlink(missing_ok=True)
