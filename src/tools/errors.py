"""Context-tool exceptions shared by the serving and mock layers."""

from __future__ import annotations


class ContextToolError(RuntimeError):
    def __init__(self, tool: str, reason: str) -> None:
        super().__init__(f"Context tool {tool} failed: {reason}")
        self.tool = tool
        self.reason = reason


class CustomerNotFoundError(ContextToolError):
    pass


class ServiceUnavailableError(ContextToolError):
    pass
