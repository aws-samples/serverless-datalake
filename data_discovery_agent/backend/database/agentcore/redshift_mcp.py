"""
AWS Redshift MCP Server for AgentCore Runtime
Uses the Redshift Data API (serverless) - no VPC connectivity required.
Provides read-only access to Redshift Serverless via Spectrum + local tables.
"""

import json
import logging
import boto3
import time
import os
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)
logger.info("Initializing Redshift MCP Server")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="redshift-mcp-server",
    instructions="""
    # AWS Redshift MCP Server
    This server provides read-only tools to interact with Amazon Redshift Serverless
    via the Redshift Data API. It supports listing schemas, tables, columns, and
    executing SELECT queries across both Spectrum (external) and local tables.
""",
    host="0.0.0.0", stateless_http=True
)

logger.info("FastMCP server instance created")

# Initialize Redshift Data API client
try:
    logger.info("Initializing Redshift Data API client...")
    redshift_data_client = boto3.client('redshift-data')
    logger.info("Redshift Data API client initialized successfully")

    # Get configuration from environment
    WORKGROUP = os.getenv('REDSHIFT_WORKGROUP', 'workshop-redshift-wg')
    DATABASE = os.getenv('REDSHIFT_DATABASE', 'analytics_db')
    logger.info(f"Using workgroup: {WORKGROUP}, database: {DATABASE}")

except Exception as e:
    logger.error(f"Failed to initialize Redshift Data API client: {e}")
    redshift_data_client = None
    WORKGROUP = ''
    DATABASE = ''


def _execute_and_wait(sql, database=None, timeout=60):
    """Execute a SQL statement via Data API and wait for results."""
    db = database or DATABASE

    response = redshift_data_client.execute_statement(
        WorkgroupName=WORKGROUP,
        Database=db,
        Sql=sql
    )

    statement_id = response['Id']
    logger.info(f"Statement ID: {statement_id}")

    # Poll for completion
    elapsed = 0
    while elapsed < timeout:
        desc = redshift_data_client.describe_statement(Id=statement_id)
        status = desc['Status']

        if status == 'FINISHED':
            break
        elif status in ('FAILED', 'ABORTED'):
            error = desc.get('Error', 'Unknown error')
            raise Exception(f"Query failed ({status}): {error}")

        time.sleep(1)
        elapsed += 1

    if elapsed >= timeout:
        raise Exception(f"Query timed out after {timeout}s")

    # Get results
    try:
        result = redshift_data_client.get_statement_result(Id=statement_id)
        return result
    except redshift_data_client.exceptions.ResourceNotFoundException:
        # No results (e.g., DDL statement)
        return None


def _format_results(result):
    """Format Data API results into rows with column names."""
    if not result:
        return {"columns": [], "rows": [], "row_count": 0}

    columns = [col['name'] for col in result.get('ColumnMetadata', [])]
    rows = []

    for record in result.get('Records', []):
        row = {}
        for i, field in enumerate(record):
            col_name = columns[i] if i < len(columns) else f'col_{i}'
            # Extract value from the typed field
            if 'stringValue' in field:
                row[col_name] = field['stringValue']
            elif 'longValue' in field:
                row[col_name] = field['longValue']
            elif 'doubleValue' in field:
                row[col_name] = field['doubleValue']
            elif 'booleanValue' in field:
                row[col_name] = field['booleanValue']
            elif 'isNull' in field and field['isNull']:
                row[col_name] = None
            else:
                row[col_name] = str(field)
        rows.append(row)

    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows)
    }


@mcp.tool()
async def test_redshift_connection() -> str:
    """
    Test the connection to Redshift Serverless via the Data API.

    Returns:
        str: Connection status message
    """
    logger.info("TEST_REDSHIFT_CONNECTION called")
    try:
        if not redshift_data_client:
            return "Redshift Data API client not initialized"

        result = _execute_and_wait("SELECT 1 AS connected")
        return f"Redshift connection successful (workgroup: {WORKGROUP}, database: {DATABASE})"
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return f"Redshift connection error: {str(e)}"


@mcp.tool()
async def get_redshift_config() -> str:
    """
    Get the current Redshift MCP server configuration.

    Returns:
        str: JSON formatted configuration
    """
    logger.info("GET_REDSHIFT_CONFIG called")
    config = {
        "workgroup": WORKGROUP,
        "database": DATABASE,
        "client_initialized": redshift_data_client is not None,
        "region": os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'not set'))
    }
    return json.dumps(config, indent=2)


@mcp.tool()
async def list_redshift_schemas(database_name: Optional[str] = None) -> str:
    """
    List all schemas in the Redshift database.

    Args:
        database_name: Database to query (default: configured database)

    Returns:
        str: JSON list of schemas
    """
    logger.info(f"LIST_REDSHIFT_SCHEMAS called")
    try:
        if not redshift_data_client:
            return "Redshift Data API client not initialized"

        sql = """
            SELECT schema_name, schema_owner, schema_type
            FROM svv_all_schemas
            WHERE database_name = current_database()
            ORDER BY schema_name
        """
        result = _execute_and_wait(sql, database=database_name)
        formatted = _format_results(result)

        return json.dumps({
            "database": database_name or DATABASE,
            "schemas": formatted["rows"],
            "count": formatted["row_count"]
        }, indent=2)
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return f"Error listing schemas: {str(e)}"


@mcp.tool()
async def list_redshift_tables(schema_name: str = "public", database_name: Optional[str] = None) -> str:
    """
    List all tables in a given schema.

    Args:
        schema_name: Schema to list tables from (default: public)
        database_name: Database to query (default: configured database)

    Returns:
        str: JSON list of tables with type info
    """
    logger.info(f"LIST_REDSHIFT_TABLES called for schema: {schema_name}")
    try:
        if not redshift_data_client:
            return "Redshift Data API client not initialized"

        sql = f"""
            SELECT table_name, table_type, table_schema
            FROM svv_all_tables
            WHERE database_name = current_database()
              AND schema_name = '{schema_name}'
            ORDER BY table_name
        """
        result = _execute_and_wait(sql, database=database_name)
        formatted = _format_results(result)

        return json.dumps({
            "database": database_name or DATABASE,
            "schema": schema_name,
            "tables": formatted["rows"],
            "count": formatted["row_count"]
        }, indent=2)
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return f"Error listing tables: {str(e)}"


@mcp.tool()
async def list_redshift_columns(table_name: str, schema_name: str = "public", database_name: Optional[str] = None) -> str:
    """
    List all columns for a specific table.

    Args:
        table_name: Table to get columns for
        schema_name: Schema the table is in (default: public)
        database_name: Database to query (default: configured database)

    Returns:
        str: JSON list of columns with data types
    """
    logger.info(f"LIST_REDSHIFT_COLUMNS called for {schema_name}.{table_name}")
    try:
        if not redshift_data_client:
            return "Redshift Data API client not initialized"

        sql = f"""
            SELECT column_name, data_type, ordinal_position, is_nullable, column_default
            FROM svv_all_columns
            WHERE database_name = current_database()
              AND schema_name = '{schema_name}'
              AND table_name = '{table_name}'
            ORDER BY ordinal_position
        """
        result = _execute_and_wait(sql, database=database_name)
        formatted = _format_results(result)

        return json.dumps({
            "database": database_name or DATABASE,
            "schema": schema_name,
            "table": table_name,
            "columns": formatted["rows"],
            "count": formatted["row_count"]
        }, indent=2)
    except Exception as e:
        logger.error(f"Error listing columns: {e}")
        return f"Error listing columns: {str(e)}"


@mcp.tool()
async def execute_redshift_query(sql: str, database_name: Optional[str] = None, limit: int = 100) -> str:
    """
    Execute a READ-ONLY SQL query against Redshift Serverless.
    Only SELECT, SHOW, and DESCRIBE statements are allowed.

    Args:
        sql: SQL query to execute (SELECT only)
        database_name: Database to query (default: configured database)
        limit: Maximum rows to return (default: 100, max: 1000)

    Returns:
        str: JSON formatted query results
    """
    logger.info(f"EXECUTE_REDSHIFT_QUERY called with sql: {sql[:100]}")
    try:
        if not redshift_data_client:
            return "Redshift Data API client not initialized"

        # Security: only allow read operations
        sql_upper = sql.strip().upper()
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("SHOW") or sql_upper.startswith("DESCRIBE")):
            return "Only SELECT, SHOW, and DESCRIBE queries are allowed (read-only mode)"

        # Apply limit if not present
        limit = min(limit, 1000)
        if "LIMIT" not in sql_upper and sql_upper.startswith("SELECT"):
            sql = f"{sql.rstrip(';')} LIMIT {limit}"

        result = _execute_and_wait(sql, database=database_name, timeout=120)
        formatted = _format_results(result)

        return json.dumps({
            "query": sql,
            "database": database_name or DATABASE,
            "columns": formatted["columns"],
            "results": formatted["rows"],
            "row_count": formatted["row_count"]
        }, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return f"Error executing query: {str(e)}"


def main():
    logger.info("Starting Redshift MCP Server with Streamable HTTP transport")
    logger.info(f"Workgroup: {WORKGROUP}, Database: {DATABASE}")
    try:
        mcp.run(transport="streamable-http")
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        raise


if __name__ == "__main__":
    main()
