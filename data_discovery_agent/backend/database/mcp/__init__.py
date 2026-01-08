"""
MCP servers module for database operations.
"""

# Athena MCP is a FastMCP server, not a class
# Import the module for access to the mcp instance and tools
from . import athena_mcp

# ClickHouse MCP is a FastMCP server, not a class
# Import the module for access to the mcp instance and tools
from . import clickhouse_mcp

__all__ = ['athena_mcp', 'clickhouse_mcp']