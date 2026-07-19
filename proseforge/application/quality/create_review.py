from __future__ import annotations

def normalize_findings(findings: list[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for finding in findings:
        severity = str(finding.get("severity", "suggestion"))
        if severity not in {"blocking", "suggestion", "nit"}:
            raise ValueError("invalid review severity")
        evidence = finding.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError("review evidence must be a list")
        result.append({"severity": severity, "message": str(finding.get("message", "")), "evidence": evidence})
    return result
