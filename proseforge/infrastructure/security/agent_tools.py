from __future__ import annotations
import re

class ToolDenied(PermissionError): pass

def authorize_tool(tool: str, allowlist: set[str], args: dict[str, object]) -> None:
    if tool not in allowlist: raise ToolDenied("tool is not allowed")
    if any(key.lower() in {"command", "shell", "url"} and str(value).startswith(("file:", "\\\\", "/etc", "C:\\")) for key, value in args.items()): raise ToolDenied("unsafe tool argument")

def redact(text: str) -> str:
    return re.sub(r"(?i)(api[_-]?key|token|password|secret)=([^\s&]+)", r"\1=[REDACTED]", text)
