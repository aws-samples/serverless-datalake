"""
Redshift MCP Server Entry Point for AgentCore Runtime.
Uses the awslabs.redshift-mcp-server package which provides:
- list_clusters, list_databases, list_schemas, list_tables, list_columns
- execute_query (READ ONLY - SELECT statements only)

Environment Variables:
  REDSHIFT_WORKGROUP: Redshift Serverless workgroup name (default: workshop-redshift-wg)
  REDSHIFT_DATABASE: Database name (default: analytics_db)
"""

import os
import sys

# Set default environment variables for the Redshift MCP server
os.environ.setdefault("REDSHIFT_WORKGROUP", "workshop-redshift-wg")
os.environ.setdefault("REDSHIFT_DATABASE", "analytics_db")
os.environ.setdefault("READONLY", "true")

# The awslabs.redshift-mcp-server package provides the MCP server implementation.
# Import and run it directly.
from awslabs.redshift_mcp_server.__main__ import main

if __name__ == "__main__":
    main()
