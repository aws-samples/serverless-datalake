"""
AWS Athena Database Tools for Strands Agents MCP Server
"""

import json
import logging
import boto3
import time
import os
from typing import Optional, Dict, Any, List
from botocore.exceptions import ClientError, BotoCoreError

# Get logger for this module
logger = logging.getLogger(__name__)

# Log startup information
logger.info("Initializing Athena MCP Server")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="athena-mcp-server",
    instructions="""
    # AWS Athena MCP Server
    This server provides tools to interact with AWS Athena for querying data lakes and databases.
    It supports listing databases, tables, executing queries, and managing query executions.
""",
host="0.0.0.0", stateless_http=True
)
DEFAULT_OUTPUT_LOCATION=None
logger.info("FastMCP server instance created")

# Initialize Athena client and get configuration
try:
    logger.info("Initializing AWS Athena client...")
    athena_client = boto3.client('athena')
    logger.info("AWS Athena client initialized successfully")
    
    # Get default output location from environment variable
    # STOP_GAP
    DEFAULT_OUTPUT_LOCATION = os.getenv('DEFAULT_S3_OUTPUT_LOCATION', '')
    if DEFAULT_OUTPUT_LOCATION:
        logger.info(f"Using default output location: {DEFAULT_OUTPUT_LOCATION}")
    else:
        logger.warning("No default output location set. Queries will require explicit output_location parameter.")
        
except Exception as e:
    logger.error(f"Failed to initialize Athena client: {e}")
    athena_client = None
    DEFAULT_OUTPUT_LOCATION = ''


@mcp.tool()
async def test_athena_connection() -> str:
    """
    Test the AWS Athena connection.

    Returns:
        str: Connection status message
    """
    print("🔌 TEST_ATHENA_CONNECTION called")
    logger.info("TEST_ATHENA_CONNECTION called")
    try:
        if not athena_client:
            print("❌ Athena client not initialized")
            return "❌ Athena client not initialized"
        
        # Test connection by listing workgroups
        response = athena_client.list_work_groups(MaxResults=1)
        print("✅ Athena connection successful")
        return "✅ Athena connection successful"
    except Exception as e:
        print(f"❌ Athena connection error: {str(e)}")
        return f"❌ Athena connection error: {str(e)}"


@mcp.tool()
async def get_athena_config() -> str:
    """
    Get the current Athena MCP server configuration.

    Returns:
        str: JSON formatted configuration information
    """
    print("⚙️ GET_ATHENA_CONFIG called")
    logger.info("GET_ATHENA_CONFIG called")
    try:
        config = {
            "default_output_location": DEFAULT_OUTPUT_LOCATION,
            "athena_client_initialized": athena_client is not None,
            "environment_variables": {
                "DEFAULT_S3_OUTPUT_LOCATION": os.getenv('DEFAULT_S3_OUTPUT_LOCATION', 'Not set'),
                "AWS_REGION": os.getenv('AWS_REGION', 'Not set'),
                "AWS_DEFAULT_REGION": os.getenv('AWS_DEFAULT_REGION', 'Not set')
            }
        }
        
        print(f"✅ Configuration retrieved successfully")
        return json.dumps(config, indent=2)
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        print(f"❌ Error getting configuration: {str(e)}")
        return f"❌ Error getting configuration: {str(e)}"


@mcp.tool()
async def list_athena_data_catalogs() -> str:
    """
    List all data catalogs available in Athena.

    Returns:
        str: JSON formatted list of data catalogs
    """
    print("📋 LIST_ATHENA_DATA_CATALOGS called")
    logger.info("LIST_ATHENA_DATA_CATALOGS called")
    try:
        if not athena_client:
            return "❌ Athena client not initialized"
        
        response = athena_client.list_data_catalogs()
        catalogs = response.get('DataCatalogsSummary', [])
        
        result = {
            "catalogs": [
                {
                    "name": catalog.get('CatalogName'),
                    "type": catalog.get('Type')
                }
                for catalog in catalogs
            ],
            "count": len(catalogs)
        }
        
        print(f"✅ Found {len(catalogs)} data catalogs")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing data catalogs: {e}")
        print(f"❌ Error listing data catalogs: {str(e)}")
        return f"❌ Error listing data catalogs: {str(e)}"


@mcp.tool()
async def list_athena_databases(catalog_name: str = "AwsDataCatalog") -> str:
    """
    List all databases in the specified Athena data catalog.

    Args:
        catalog_name (str): Name of the data catalog (default: AwsDataCatalog)

    Returns:
        str: JSON formatted list of databases
    """
    print(f"📋 LIST_ATHENA_DATABASES called with catalog: {catalog_name}")
    logger.info(f"LIST_ATHENA_DATABASES called with catalog: {catalog_name}")
    try:
        if not athena_client:
            return "❌ Athena client not initialized"
        
        response = athena_client.list_databases(CatalogName=catalog_name)
        databases = response.get('DatabaseList', [])
        
        result = {
            "catalog": catalog_name,
            "databases": [
                {
                    "name": db.get('Name'),
                    "description": db.get('Description', ''),
                    "parameters": db.get('Parameters', {})
                }
                for db in databases
            ],
            "count": len(databases)
        }
        
        print(f"✅ Found {len(databases)} databases in catalog '{catalog_name}'")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing databases: {e}")
        print(f"❌ Error listing databases: {str(e)}")
        return f"❌ Error listing databases: {str(e)}"


@mcp.tool()
async def list_athena_tables(database_name: str, catalog_name: str = "AwsDataCatalog") -> str:
    """
    List all tables in the specified Athena database.

    Args:
        database_name (str): Name of the database
        catalog_name (str): Name of the data catalog (default: AwsDataCatalog)

    Returns:
        str: JSON formatted list of tables with metadata
    """
    print(f"📋 LIST_ATHENA_TABLES called for database: {database_name}, catalog: {catalog_name}")
    logger.info(f"LIST_ATHENA_TABLES called for database: {database_name}, catalog: {catalog_name}")
    try:
        if not athena_client:
            return "❌ Athena client not initialized"
        
        response = athena_client.list_table_metadata(
            CatalogName=catalog_name,
            DatabaseName=database_name
        )
        tables = response.get('TableMetadataList', [])
        
        result = {
            "catalog": catalog_name,
            "database": database_name,
            "tables": [],
            "count": len(tables)
        }
        
        for table in tables:
            table_info = {
                "name": table.get('Name'),
                "table_type": table.get('TableType'),
                "create_time": table.get('CreateTime').isoformat() if table.get('CreateTime') else None,
                "last_access_time": table.get('LastAccessTime').isoformat() if table.get('LastAccessTime') else None,
                "columns": [
                    {
                        "name": col.get('Name'),
                        "type": col.get('Type'),
                        "comment": col.get('Comment', '')
                    }
                    for col in table.get('Columns', [])
                ],
                "partition_keys": [
                    {
                        "name": key.get('Name'),
                        "type": key.get('Type'),
                        "comment": key.get('Comment', '')
                    }
                    for key in table.get('PartitionKeys', [])
                ],
                "parameters": table.get('Parameters', {})
            }
            result["tables"].append(table_info)
        
        print(f"✅ Found {len(tables)} tables in database '{database_name}'")
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        print(f"❌ Error listing tables: {str(e)}")
        return f"❌ Error listing tables: {str(e)}"


@mcp.tool()
async def get_athena_table_metadata(
    table_name: str, 
    database_name: str, 
    catalog_name: str = "AwsDataCatalog"
) -> str:
    """
    Get detailed metadata for a specific Athena table.

    Args:
        table_name (str): Name of the table
        database_name (str): Name of the database
        catalog_name (str): Name of the data catalog (default: AwsDataCatalog)

    Returns:
        str: JSON formatted table metadata
    """
    print(f"📊 GET_ATHENA_TABLE_METADATA called for table: {table_name}, database: {database_name}")
    logger.info(f"GET_ATHENA_TABLE_METADATA called for table: {table_name}, database: {database_name}")
    try:
        if not athena_client:
            return "❌ Athena client not initialized"
        
        response = athena_client.get_table_metadata(
            CatalogName=catalog_name,
            DatabaseName=database_name,
            TableName=table_name
        )
        
        table_metadata = response.get('TableMetadata', {})
        
        result = {
            "catalog": catalog_name,
            "database": database_name,
            "table": {
                "name": table_metadata.get('Name'),
                "table_type": table_metadata.get('TableType'),
                "create_time": table_metadata.get('CreateTime').isoformat() if table_metadata.get('CreateTime') else None,
                "last_access_time": table_metadata.get('LastAccessTime').isoformat() if table_metadata.get('LastAccessTime') else None,
                "columns": [
                    {
                        "name": col.get('Name'),
                        "type": col.get('Type'),
                        "comment": col.get('Comment', '')
                    }
                    for col in table_metadata.get('Columns', [])
                ],
                "partition_keys": [
                    {
                        "name": key.get('Name'),
                        "type": key.get('Type'),
                        "comment": key.get('Comment', '')
                    }
                    for key in table_metadata.get('PartitionKeys', [])
                ],
                "parameters": table_metadata.get('Parameters', {}),
                "location": table_metadata.get('Parameters', {}).get('location', ''),
                "input_format": table_metadata.get('Parameters', {}).get('inputformat', ''),
                "output_format": table_metadata.get('Parameters', {}).get('outputformat', ''),
                "serde_info": table_metadata.get('Parameters', {}).get('serde.serialization.lib', '')
            }
        }
        
        print(f"✅ Retrieved metadata for table '{table_name}'")
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error getting table metadata: {e}")
        print(f"❌ Error getting table metadata for '{table_name}': {str(e)}")
        return f"❌ Error getting table metadata for '{table_name}': {str(e)}"


@mcp.tool()
async def execute_athena_query(
    query: str,
    database_name: str,
    catalog_name: str = "AwsDataCatalog",
    workgroup: str = "primary",
    limit: int = 100
) -> str:
    """
    Execute a query in AWS Athena and return the results.

    Args:
        query (str): SQL query to execute
        database_name (str): Database to execute the query against
        catalog_name (str): Data catalog name (default: AwsDataCatalog)
        workgroup (str): Athena workgroup (default: primary)
        limit (int, optional): Maximum number of rows to return (default: 100)

    Returns:
        str: JSON formatted query results
    """
    print(f"🔍 EXECUTE_ATHENA_QUERY called with query: {query[:100]}{'...' if len(query) > 100 else ''}")
    logger.info(f"EXECUTE_ATHENA_QUERY called with query length: {len(query)}")
    try:
        if not athena_client:
            return "❌ Athena client not initialized"
        
        # Use default output location from environment or fail
        output_location = os.getenv('DEFAULT_S3_OUTPUT_LOCATION', '')
        if not output_location:
            return "❌ No output location provided and no default configured. Please provide an S3 output location (e.g., s3://bucket/path/) by setting DEFAULT_S3_OUTPUT_LOCATION environment variable"
        
        # Use workgroup from environment variable if set, otherwise use the parameter
        workgroup_to_use = os.getenv("WORKGROUP", workgroup)
        print(f"📍 Using workgroup: {workgroup_to_use}")
        logger.info(f"Using workgroup: {workgroup_to_use}")
        
        # Security check - only allow SELECT queries
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT") and not query_upper.startswith("SHOW") and not query_upper.startswith("DESCRIBE"):
            print("❌ Only SELECT, SHOW, and DESCRIBE queries are allowed for security reasons")
            return "❌ Only SELECT, SHOW, and DESCRIBE queries are allowed for security reasons"
        
        # Apply limit if not already present and it's a SELECT query
        if limit and "LIMIT" not in query_upper and query_upper.startswith("SELECT"):
            limit = min(limit, 1000)  # Cap at 1000 rows
            query = f"{query.rstrip(';')} LIMIT {limit}"
        
        # Start query execution
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={
                'Database': database_name,
                'Catalog': catalog_name
            },
            ResultConfiguration={
                'OutputLocation': output_location
            },
            WorkGroup=workgroup_to_use
        )
        
        query_execution_id = response['QueryExecutionId']
        print(f"🚀 Query started with execution ID: {query_execution_id}")
        
        # Wait for query to complete
        max_wait_time = 300  # 5 minutes
        wait_time = 0
        while wait_time < max_wait_time:
            execution_response = athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            
            status = execution_response['QueryExecution']['Status']['State']
            
            if status in ['SUCCEEDED']:
                break
            elif status in ['FAILED', 'CANCELLED']:
                error_msg = execution_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                print(f"❌ Query failed: {error_msg}")
                return f"❌ Query failed: {error_msg}"
            
            time.sleep(2)
            wait_time += 2
        
        if wait_time >= max_wait_time:
            print("❌ Query timed out")
            return "❌ Query execution timed out"
        
        # Get query results
        results_response = athena_client.get_query_results(
            QueryExecutionId=query_execution_id,
            MaxResults=limit if limit else 100
        )
        
        # Parse results
        result_set = results_response.get('ResultSet', {})
        rows = result_set.get('Rows', [])
        
        if not rows:
            print("✅ Query executed successfully but returned no results")
            return json.dumps({
                "query": query,
                "execution_id": query_execution_id,
                "row_count": 0,
                "results": [],
                "columns": []
            }, indent=2)
        
        # Extract column names from first row (header)
        columns = [col.get('VarCharValue', '') for col in rows[0].get('Data', [])]
        
        # Extract data rows
        data_rows = []
        for row in rows[1:]:  # Skip header row
            row_data = {}
            for i, col_data in enumerate(row.get('Data', [])):
                column_name = columns[i] if i < len(columns) else f'column_{i}'
                row_data[column_name] = col_data.get('VarCharValue', '')
            data_rows.append(row_data)
        
        result = {
            "query": query,
            "execution_id": query_execution_id,
            "database": database_name,
            "catalog": catalog_name,
            "row_count": len(data_rows),
            "columns": columns,
            "results": data_rows
        }
        
        print(f"✅ Query executed successfully, returned {len(data_rows)} rows")
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        print(f"❌ Query execution error: {str(e)}")
        return f"❌ Query execution error: {str(e)}"


@mcp.tool()
async def get_athena_query_execution(query_execution_id: str) -> str:
    """
    Get details about a specific query execution.

    Args:
        query_execution_id (str): The query execution ID

    Returns:
        str: JSON formatted query execution details
    """
    print(f"📊 GET_ATHENA_QUERY_EXECUTION called for ID: {query_execution_id}")
    logger.info(f"GET_ATHENA_QUERY_EXECUTION called for ID: {query_execution_id}")
    try:
        if not athena_client:
            return "❌ Athena client not initialized"
        
        response = athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        
        query_execution = response.get('QueryExecution', {})
        
        result = {
            "query_execution_id": query_execution.get('QueryExecutionId'),
            "query": query_execution.get('Query'),
            "status": {
                "state": query_execution.get('Status', {}).get('State'),
                "state_change_reason": query_execution.get('Status', {}).get('StateChangeReason'),
                "submission_date_time": query_execution.get('Status', {}).get('SubmissionDateTime').isoformat() if query_execution.get('Status', {}).get('SubmissionDateTime') else None,
                "completion_date_time": query_execution.get('Status', {}).get('CompletionDateTime').isoformat() if query_execution.get('Status', {}).get('CompletionDateTime') else None
            },
            "statistics": {
                "engine_execution_time_in_millis": query_execution.get('Statistics', {}).get('EngineExecutionTimeInMillis'),
                "data_processed_in_bytes": query_execution.get('Statistics', {}).get('DataProcessedInBytes'),
                "data_scanned_in_bytes": query_execution.get('Statistics', {}).get('DataScannedInBytes'),
                "query_queue_time_in_millis": query_execution.get('Statistics', {}).get('QueryQueueTimeInMillis'),
                "query_planning_time_in_millis": query_execution.get('Statistics', {}).get('QueryPlanningTimeInMillis'),
                "service_processing_time_in_millis": query_execution.get('Statistics', {}).get('ServiceProcessingTimeInMillis')
            },
            "query_execution_context": query_execution.get('QueryExecutionContext', {}),
            "result_configuration": query_execution.get('ResultConfiguration', {}),
            "workgroup": query_execution.get('WorkGroup')
        }
        
        print(f"✅ Retrieved query execution details for ID: {query_execution_id}")
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error getting query execution: {e}")
        print(f"❌ Error getting query execution: {str(e)}")
        return f"❌ Error getting query execution: {str(e)}"


@mcp.tool()
async def list_athena_query_executions(workgroup: str = "primary", max_results: int = 50) -> str:
    """
    List recent query executions in the specified workgroup.

    Args:
        workgroup (str): Athena workgroup (default: primary)
        max_results (int): Maximum number of results to return (default: 50)

    Returns:
        str: JSON formatted list of query executions
    """
    print(f"📋 LIST_ATHENA_QUERY_EXECUTIONS called for workgroup: {workgroup}")
    logger.info(f"LIST_ATHENA_QUERY_EXECUTIONS called for workgroup: {workgroup}")
    try:
        if not athena_client:
            return "❌ Athena client not initialized"
        
        response = athena_client.list_query_executions(
            WorkGroup=workgroup,
            MaxResults=min(max_results, 50)
        )
        
        query_execution_ids = response.get('QueryExecutionIds', [])
        
        # Get details for each query execution
        executions = []
        for execution_id in query_execution_ids:
            try:
                exec_response = athena_client.get_query_execution(
                    QueryExecutionId=execution_id
                )
                query_execution = exec_response.get('QueryExecution', {})
                
                executions.append({
                    "query_execution_id": execution_id,
                    "query": query_execution.get('Query', '')[:100] + ('...' if len(query_execution.get('Query', '')) > 100 else ''),
                    "state": query_execution.get('Status', {}).get('State'),
                    "submission_date_time": query_execution.get('Status', {}).get('SubmissionDateTime').isoformat() if query_execution.get('Status', {}).get('SubmissionDateTime') else None,
                    "completion_date_time": query_execution.get('Status', {}).get('CompletionDateTime').isoformat() if query_execution.get('Status', {}).get('CompletionDateTime') else None,
                    "data_scanned_in_bytes": query_execution.get('Statistics', {}).get('DataScannedInBytes'),
                    "engine_execution_time_in_millis": query_execution.get('Statistics', {}).get('EngineExecutionTimeInMillis')
                })
            except Exception as e:
                logger.warning(f"Error getting details for execution {execution_id}: {e}")
                executions.append({
                    "query_execution_id": execution_id,
                    "error": f"Could not retrieve details: {str(e)}"
                })
        
        result = {
            "workgroup": workgroup,
            "executions": executions,
            "count": len(executions)
        }
        
        print(f"✅ Found {len(executions)} query executions in workgroup '{workgroup}'")
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error listing query executions: {e}")
        print(f"❌ Error listing query executions: {str(e)}")
        return f"❌ Error listing query executions: {str(e)}"


#@mcp.tool()
async def get_athena_database_summary(catalog_name: str = "AwsDataCatalog") -> str:
    """
    Get a comprehensive summary of all databases and tables in the Athena catalog.

    Args:
        catalog_name (str): Name of the data catalog (default: AwsDataCatalog)

    Returns:
        str: JSON formatted summary of the entire catalog
    """
    print(f"📋 GET_ATHENA_DATABASE_SUMMARY called for catalog: {catalog_name}")
    logger.info(f"GET_ATHENA_DATABASE_SUMMARY called for catalog: {catalog_name}")
    try:
        if not athena_client:
            return "❌ Athena client not initialized"
        
        # Get all databases
        databases_response = athena_client.list_databases(CatalogName=catalog_name)
        databases = databases_response.get('DatabaseList', [])
        
        summary = {
            "catalog": catalog_name,
            "database_count": len(databases),
            "databases": [],
            "total_tables": 0
        }
        
        for db in databases:
            db_name = db.get('Name')
            db_info = {
                "name": db_name,
                "description": db.get('Description', ''),
                "parameters": db.get('Parameters', {}),
                "tables": [],
                "table_count": 0
            }
            
            try:
                # Get tables for this database
                tables_response = athena_client.list_table_metadata(
                    CatalogName=catalog_name,
                    DatabaseName=db_name
                )
                tables = tables_response.get('TableMetadataList', [])
                
                for table in tables:
                    table_info = {
                        "name": table.get('Name'),
                        "table_type": table.get('TableType'),
                        "column_count": len(table.get('Columns', [])),
                        "partition_key_count": len(table.get('PartitionKeys', [])),
                        "create_time": table.get('CreateTime').isoformat() if table.get('CreateTime') else None,
                        "location": table.get('Parameters', {}).get('location', '')
                    }
                    db_info["tables"].append(table_info)
                
                db_info["table_count"] = len(tables)
                summary["total_tables"] += len(tables)
                
            except Exception as e:
                logger.warning(f"Error getting tables for database {db_name}: {e}")
                db_info["error"] = f"Could not retrieve tables: {str(e)}"
            
            summary["databases"].append(db_info)
        
        print(f"✅ Generated summary for catalog '{catalog_name}' with {len(databases)} databases and {summary['total_tables']} total tables")
        return json.dumps(summary, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error getting database summary: {e}")
        print(f"❌ Error getting database summary: {str(e)}")
        return f"❌ Error getting database summary: {str(e)}"


def main():
    logger.info("Starting Athena MCP Server with Streamable HTTP transport")
    logger.info("Server will be available at http://localhost:8000/mcp")
    try:
        mcp.run(transport="streamable-http")
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        raise


if __name__ == "__main__":
    main()