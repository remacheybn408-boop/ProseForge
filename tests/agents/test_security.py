import pytest
from proseforge.infrastructure.security.agent_tools import ToolDenied, authorize_tool, redact

def test_tool_policy_fails_closed_and_redacts_secrets():
    with pytest.raises(ToolDenied): authorize_tool("shell", {"http"}, {})
    with pytest.raises(ToolDenied): authorize_tool("http", {"http"}, {"url": "file:///etc/passwd"})
    assert "secret=[REDACTED]" in redact("secret=abc")
