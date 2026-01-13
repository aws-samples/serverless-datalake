"""
Database hooks module for MCP agents.
"""

from .approval_hooks import MCPToolApprovalHook
from .graph_tool_hook import GraphToolHook
__all__ = ['MCPToolApprovalHook', 'GraphToolHook']