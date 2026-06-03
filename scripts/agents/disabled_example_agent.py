"""
Example agent — disabled by default.
Shows how to subclass BaseAgent for future multi-agent systems.
"""

from .base_agent import BaseAgent

class ExampleAgent(BaseAgent):
    """Example agent showing the intended interface pattern."""
    
    def __init__(self):
        super().__init__(name="example_agent")
    
    def review(self, content: str, context: dict = None) -> dict:
        if not self.enabled:
            return super().review(content, context)
        # Future: actual guard logic here
        return {"status": "PASS", "findings": []}
