"""
ClickHouse Database Tools for Strands Agents MCP Server
"""

import json
import logging
import time
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP
import clickhouse_connect
from clickhouse_connect.driver.exceptions import DatabaseError, OperationalError

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "clickhouse-mcp-server",
    instructions="""
    # ClickHouse MCP Server
    This server provides tools to interact with ClickHouse databases for high-performance analytics.
    It supports listing databases, tables, executing queries, and managing ClickHouse-specific operations.
""",
    host="0.0.0.0",
    port=8002,
)

# ClickHouse connection configuration
CLICKHOUSE_CONFIG = {
    'host': 'localhost',
    'port': 8123,
    'username': 'default',
    'password': '',
    'database': 'default'
}

# Global client instance
clickhouse_client = None


def get_clickhouse_client():
    """Get or create ClickHouse client connection."""
    global clickhouse_client
    if clickhouse_client is None:
        try:
            clickhouse_client = clickhouse_connect.get_client(
                host=CLICKHOUSE_CONFIG['host'],
                port=CLICKHOUSE_CONFIG['port'],
                username=CLICKHOUSE_CONFIG['username'],
                password=CLICKHOUSE_CONFIG['password'],
                database=CLICKHOUSE_CONFIG['database']
            )
            logger.info("ClickHouse client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ClickHouse client: {e}")
            clickhouse_client = None
    return clickhouse_client


@mcp.tool()
async def test_clickhouse_connection() -> str:
    """
    Test the ClickHouse database connection.

    Returns:
        str: Connection status message
    """
    print("🔌 TEST_CLICKHOUSE_CONNECTION called")
    logger.info("TEST_CLICKHOUSE_CONNECTION called")
    try:
        client = get_clickhouse_client()
        if not client:
            print("❌ ClickHouse client not initialized")
            return "❌ ClickHouse client not initialized"
        
        # Test connection with a simple query
        result = client.query("SELECT 1 as test")
        if result.result_rows and result.result_rows[0][0] == 1:
            print("✅ ClickHouse connection successful")
            return "✅ ClickHouse connection successful"
        else:
            print("❌ ClickHouse connection test failed")
            return "❌ ClickHouse connection test failed"
    except Exception as e:
        print(f"❌ ClickHouse connection error: {str(e)}")
        return f"❌ ClickHouse connection error: {str(e)}"


@mcp.tool()
async def list_clickhouse_databases() -> str:
    """
    List all databases in the ClickHouse instance.

    Returns:
        str: JSON formatted list of databases
    """
    print("📋 LIST_CLICKHOUSE_DATABASES called")
    logger.info("LIST_CLICKHOUSE_DATABASES called")
    try:
        client = get_clickhouse_client()
        if not client:
            return "❌ ClickHouse client not initialized"
        
        result = client.query("SHOW DATABASES")
        databases = [row[0] for row in result.result_rows]
        
        # Get additional database information
        database_info = []
        for db_name in databases:
            try:
                # Get database engine info
                engine_result = client.query(f"SELECT engine FROM system.databases WHERE name = '{db_name}'")
                engine = engine_result.result_rows[0][0] if engine_result.result_rows else 'Unknown'
                
                database_info.append({
                    "name": db_name,
                    "engine": engine
                })
            except Exception as e:
                logger.warning(f"Could not get engine info for database {db_name}: {e}")
                database_info.append({
                    "name": db_name,
                    "engine": "Unknown"
                })
        
        result_data = {
            "databases": database_info,
            "count": len(databases)
        }
        
        print(f"✅ Found {len(databases)} databases")
        return json.dumps(result_data, indent=2)
    except Exception as e:
        logger.error(f"Error listing databases: {e}")
        print(f"❌ Error listing databases: {str(e)}")
        return f"❌ Error listing databases: {str(e)}"


@mcp.tool()
async def list_clickhouse_tables(database_name: str = "default") -> str:
    """
    List all tables in the specified ClickHouse database.

    Args:
        database_name (str): Name of the database (default: default)

    Returns:
        str: JSON formatted list of tables with metadata
    """
    print(f"📋 LIST_CLICKHOUSE_TABLES called for database: {database_name}")
    logger.info(f"LIST_CLICKHOUSE_TABLES called for database: {database_name}")
    try:
        client = get_clickhouse_client()
        if not client:
            return "❌ ClickHouse client not initialized"
        
        # Get tables with detailed information
        query = f"""
        SELECT 
            name,
            engine,
            total_rows,
            total_bytes,
            formatReadableSize(total_bytes) as size_readable,
            create_table_query
        FROM system.tables 
        WHERE database = '{database_name}'
        ORDER BY name
        """
        
        result = client.query(query)
        
        tables = []
        for row in result.result_rows:
            table_info = {
                "name": row[0],
                "engine": row[1],
                "total_rows": row[2],
                "total_bytes": row[3],
                "size_readable": row[4],
                "create_table_query": row[5][:200] + "..." if len(str(row[5])) > 200 else row[5]  # Truncate long queries
            }
            tables.append(table_info)
        
        # Get column information for each table
        for table in tables:
            try:
                columns_query = f"""
                SELECT 
                    name,
                    type,
                    default_kind,
                    default_expression,
                    comment
                FROM system.columns 
                WHERE database = '{database_name}' AND table = '{table['name']}'
                ORDER BY position
                """
                columns_result = client.query(columns_query)
                
                table["columns"] = [
                    {
                        "name": col[0],
                        "type": col[1],
                        "default_kind": col[2],
                        "default_expression": col[3],
                        "comment": col[4]
                    }
                    for col in columns_result.result_rows
                ]
            except Exception as e:
                logger.warning(f"Could not get columns for table {table['name']}: {e}")
                table["columns"] = []
        
        result_data = {
            "database": database_name,
            "tables": tables,
            "count": len(tables)
        }
        
        print(f"✅ Found {len(tables)} tables in database '{database_name}'")
        return json.dumps(result_data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        print(f"❌ Error listing tables: {str(e)}")
        return f"❌ Error listing tables: {str(e)}"


@mcp.tool()
async def describe_clickhouse_table(
    table_name: str, 
    database_name: str = "default"
) -> str:
    """
    Get detailed information about a specific ClickHouse table.

    Args:
        table_name (str): Name of the table
        database_name (str): Name of the database (default: default)

    Returns:
        str: JSON formatted table information
    """
    print(f"📊 DESCRIBE_CLICKHOUSE_TABLE called for table: {table_name}, database: {database_name}")
    logger.info(f"DESCRIBE_CLICKHOUSE_TABLE called for table: {table_name}, database: {database_name}")
    try:
        client = get_clickhouse_client()
        if not client:
            return "❌ ClickHouse client not initialized"
        
        # Get table metadata
        table_query = f"""
        SELECT 
            name,
            engine,
            partition_key,
            sorting_key,
            primary_key,
            sampling_key,
            storage_policy,
            total_rows,
            total_bytes,
            formatReadableSize(total_bytes) as size_readable,
            create_table_query
        FROM system.tables 
        WHERE database = '{database_name}' AND name = '{table_name}'
        """
        
        table_result = client.query(table_query)
        if not table_result.result_rows:
            print(f"❌ Table '{table_name}' not found in database '{database_name}'")
            return f"❌ Table '{table_name}' not found in database '{database_name}'"
        
        table_row = table_result.result_rows[0]
        
        # Get column information
        columns_query = f"""
        SELECT 
            name,
            type,
            default_kind,
            default_expression,
            comment,
            codec_expression,
            ttl_expression
        FROM system.columns 
        WHERE database = '{database_name}' AND table = '{table_name}'
        ORDER BY position
        """
        columns_result = client.query(columns_query)
        
        columns = [
            {
                "name": col[0],
                "type": col[1],
                "default_kind": col[2],
                "default_expression": col[3],
                "comment": col[4],
                "codec_expression": col[5],
                "ttl_expression": col[6]
            }
            for col in columns_result.result_rows
        ]
        
        # Get partitions information
        partitions_query = f"""
        SELECT 
            partition,
            name,
            active,
            marks,
            rows,
            bytes_on_disk,
            formatReadableSize(bytes_on_disk) as size_readable
        FROM system.parts 
        WHERE database = '{database_name}' AND table = '{table_name}' AND active = 1
        ORDER BY partition
        LIMIT 10
        """
        
        try:
            partitions_result = client.query(partitions_query)
            partitions = [
                {
                    "partition": part[0],
                    "name": part[1],
                    "active": part[2],
                    "marks": part[3],
                    "rows": part[4],
                    "bytes_on_disk": part[5],
                    "size_readable": part[6]
                }
                for part in partitions_result.result_rows
            ]
        except Exception as e:
            logger.warning(f"Could not get partitions info: {e}")
            partitions = []
        
        table_info = {
            "database": database_name,
            "table": {
                "name": table_row[0],
                "engine": table_row[1],
                "partition_key": table_row[2],
                "sorting_key": table_row[3],
                "primary_key": table_row[4],
                "sampling_key": table_row[5],
                "storage_policy": table_row[6],
                "total_rows": table_row[7],
                "total_bytes": table_row[8],
                "size_readable": table_row[9],
                "create_table_query": table_row[10]
            },
            "columns": columns,
            "partitions": partitions,
            "partition_count": len(partitions)
        }
        
        print(f"✅ Retrieved detailed info for table '{table_name}'")
        return json.dumps(table_info, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error describing table: {e}")
        print(f"❌ Error describing table '{table_name}': {str(e)}")
        return f"❌ Error describing table '{table_name}': {str(e)}"


@mcp.tool()
async def execute_clickhouse_query(
    query: str,
    database_name: str = "default",
    limit: Optional[int] = 100,
    format: str = "JSONEachRow"
) -> str:
    """
    Execute a query in ClickHouse and return the results.

    Args:
        query (str): SQL query to execute
        database_name (str): Database to execute the query against (default: default)
        limit (int, optional): Maximum number of rows to return (default: 100, max: 1000)
        format (str): ClickHouse output format (default: JSONEachRow)

    Returns:
        str: JSON formatted query results
    """
    print(f"🔍 EXECUTE_CLICKHOUSE_QUERY called with query: {query[:100]}{'...' if len(query) > 100 else ''}")
    logger.info(f"EXECUTE_CLICKHOUSE_QUERY called with query length: {len(query)}")
    try:
        client = get_clickhouse_client()
        if not client:
            return "❌ ClickHouse client not initialized"
        
        # Security check - only allow SELECT, SHOW, DESCRIBE, and EXPLAIN queries
        query_upper = query.strip().upper()
        allowed_prefixes = ["SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "WITH"]
        if not any(query_upper.startswith(prefix) for prefix in allowed_prefixes):
            print("❌ Only SELECT, SHOW, DESCRIBE, EXPLAIN, and WITH queries are allowed for security reasons")
            return "❌ Only SELECT, SHOW, DESCRIBE, EXPLAIN, and WITH queries are allowed for security reasons"
        
        # Apply limit if not already present and it's a SELECT query
        if limit and "LIMIT" not in query_upper and query_upper.startswith("SELECT"):
            limit = min(limit, 1000)  # Cap at 1000 rows
            query = f"{query.rstrip(';')} LIMIT {limit}"
        
        # Execute query with timing
        start_time = time.time()
        result = client.query(query, settings={'database': database_name})
        execution_time = time.time() - start_time
        
        # Convert results to list of dictionaries
        if result.column_names and result.result_rows:
            results = []
            for row in result.result_rows:
                row_dict = {}
                for i, column_name in enumerate(result.column_names):
                    row_dict[column_name] = row[i] if i < len(row) else None
                results.append(row_dict)
        else:
            results = []
        
        # Get query statistics if available
        try:
            stats_query = "SELECT * FROM system.query_log WHERE query = {query:String} ORDER BY event_time DESC LIMIT 1"
            stats_result = client.query(stats_query, parameters={'query': query})
            query_stats = {}
            if stats_result.result_rows:
                stats_row = stats_result.result_rows[0]
                query_stats = {
                    "read_rows": stats_row[stats_result.column_names.index('read_rows')] if 'read_rows' in stats_result.column_names else 0,
                    "read_bytes": stats_row[stats_result.column_names.index('read_bytes')] if 'read_bytes' in stats_result.column_names else 0,
                    "written_rows": stats_row[stats_result.column_names.index('written_rows')] if 'written_rows' in stats_result.column_names else 0,
                    "written_bytes": stats_row[stats_result.column_names.index('written_bytes')] if 'written_bytes' in stats_result.column_names else 0,
                    "memory_usage": stats_row[stats_result.column_names.index('memory_usage')] if 'memory_usage' in stats_result.column_names else 0
                }
        except Exception as e:
            logger.warning(f"Could not get query statistics: {e}")
            query_stats = {}
        
        result_data = {
            "query": query,
            "database": database_name,
            "execution_time_seconds": round(execution_time, 3),
            "row_count": len(results),
            "columns": result.column_names if result.column_names else [],
            "results": results,
            "statistics": query_stats
        }
        
        print(f"✅ Query executed successfully, returned {len(results)} rows in {execution_time:.3f}s")
        return json.dumps(result_data, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        print(f"❌ Query execution error: {str(e)}")
        return f"❌ Query execution error: {str(e)}"


@mcp.tool()
async def get_clickhouse_table_sample(
    table_name: str,
    database_name: str = "default",
    limit: int = 5
) -> str:
    """
    Get a sample of data from a ClickHouse table.

    Args:
        table_name (str): Name of the table to sample
        database_name (str): Name of the database (default: default)
        limit (int): Number of sample rows to return (default: 5, max: 50)

    Returns:
        str: JSON formatted sample data
    """
    print(f"📊 GET_CLICKHOUSE_TABLE_SAMPLE called for {database_name}.{table_name}, limit: {limit}")
    logger.info(f"GET_CLICKHOUSE_TABLE_SAMPLE called for {database_name}.{table_name}, limit: {limit}")
    try:
        client = get_clickhouse_client()
        if not client:
            return "❌ ClickHouse client not initialized"
        
        # Ensure limit doesn't exceed maximum
        limit = min(limit, 50)
        
        # Use SAMPLE for large tables, regular LIMIT for smaller ones
        query = f"SELECT * FROM `{database_name}`.`{table_name}` LIMIT {limit}"
        
        result = client.query(query)
        
        # Convert results to list of dictionaries
        results = []
        if result.column_names and result.result_rows:
            for row in result.result_rows:
                row_dict = {}
                for i, column_name in enumerate(result.column_names):
                    row_dict[column_name] = row[i] if i < len(row) else None
                results.append(row_dict)
        
        result_data = {
            "database": database_name,
            "table": table_name,
            "sample_size": len(results),
            "columns": result.column_names if result.column_names else [],
            "data": results
        }
        
        print(f"✅ Retrieved {len(results)} sample rows from {table_name}")
        return json.dumps(result_data, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error getting table sample: {e}")
        print(f"❌ Error getting sample from table '{table_name}': {str(e)}")
        return f"❌ Error getting sample from table '{table_name}': {str(e)}"


@mcp.tool()
async def get_clickhouse_system_info() -> str:
    """
    Get ClickHouse system information and performance metrics.

    Returns:
        str: JSON formatted system information
    """
    print("🔧 GET_CLICKHOUSE_SYSTEM_INFO called")
    logger.info("GET_CLICKHOUSE_SYSTEM_INFO called")
    try:
        client = get_clickhouse_client()
        if not client:
            return "❌ ClickHouse client not initialized"
        
        # Get version info
        version_result = client.query("SELECT version()")
        version = version_result.result_rows[0][0] if version_result.result_rows else "Unknown"
        
        # Get uptime
        uptime_result = client.query("SELECT uptime()")
        uptime = uptime_result.result_rows[0][0] if uptime_result.result_rows else 0
        
        # Get current queries
        queries_result = client.query("SELECT count() FROM system.processes")
        current_queries = queries_result.result_rows[0][0] if queries_result.result_rows else 0
        
        # Get memory usage
        memory_result = client.query("""
        SELECT 
            formatReadableSize(sum(memory_usage)) as total_memory_usage,
            count() as query_count
        FROM system.processes
        """)
        
        if memory_result.result_rows:
            total_memory = memory_result.result_rows[0][0]
            query_count = memory_result.result_rows[0][1]
        else:
            total_memory = "0 B"
            query_count = 0
        
        # Get database sizes
        db_sizes_result = client.query("""
        SELECT 
            database,
            count() as table_count,
            sum(total_rows) as total_rows,
            formatReadableSize(sum(total_bytes)) as total_size
        FROM system.tables 
        WHERE database NOT IN ('system', 'information_schema', 'INFORMATION_SCHEMA')
        GROUP BY database
        ORDER BY sum(total_bytes) DESC
        """)
        
        databases = []
        for row in db_sizes_result.result_rows:
            databases.append({
                "name": row[0],
                "table_count": row[1],
                "total_rows": row[2],
                "total_size": row[3]
            })
        
        system_info = {
            "version": version,
            "uptime_seconds": uptime,
            "current_queries": current_queries,
            "total_memory_usage": total_memory,
            "active_query_count": query_count,
            "databases": databases,
            "database_count": len(databases)
        }
        
        print("✅ Retrieved ClickHouse system information")
        return json.dumps(system_info, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        print(f"❌ Error getting system info: {str(e)}")
        return f"❌ Error getting system info: {str(e)}"


@mcp.tool()
async def get_clickhouse_database_summary() -> str:
    """
    Get a comprehensive summary of all databases and tables in ClickHouse.

    Returns:
        str: JSON formatted database summary
    """
    print("📋 GET_CLICKHOUSE_DATABASE_SUMMARY called")
    logger.info("GET_CLICKHOUSE_DATABASE_SUMMARY called")
    try:
        client = get_clickhouse_client()
        if not client:
            return "❌ ClickHouse client not initialized"
        
        # Get all databases
        databases_result = client.query("SHOW DATABASES")
        databases = [row[0] for row in databases_result.result_rows]
        
        summary = {
            "clickhouse_version": "",
            "database_count": len(databases),
            "databases": [],
            "total_tables": 0,
            "total_rows": 0,
            "total_size_bytes": 0
        }
        
        # Get version
        try:
            version_result = client.query("SELECT version()")
            summary["clickhouse_version"] = version_result.result_rows[0][0] if version_result.result_rows else "Unknown"
        except:
            summary["clickhouse_version"] = "Unknown"
        
        for db_name in databases:
            if db_name in ['system', 'information_schema', 'INFORMATION_SCHEMA']:
                continue  # Skip system databases
                
            db_info = {
                "name": db_name,
                "tables": [],
                "table_count": 0,
                "total_rows": 0,
                "total_bytes": 0
            }
            
            try:
                # Get tables for this database
                tables_query = f"""
                SELECT 
                    name,
                    engine,
                    total_rows,
                    total_bytes,
                    formatReadableSize(total_bytes) as size_readable
                FROM system.tables 
                WHERE database = '{db_name}'
                ORDER BY total_bytes DESC
                """
                
                tables_result = client.query(tables_query)
                
                for table_row in tables_result.result_rows:
                    table_info = {
                        "name": table_row[0],
                        "engine": table_row[1],
                        "total_rows": table_row[2],
                        "total_bytes": table_row[3],
                        "size_readable": table_row[4]
                    }
                    
                    # Get sample data for each table
                    try:
                        sample_query = f"SELECT * FROM `{db_name}`.`{table_row[0]}` LIMIT 3"
                        sample_result = client.query(sample_query)
                        
                        sample_data = []
                        if sample_result.column_names and sample_result.result_rows:
                            for row in sample_result.result_rows:
                                row_dict = {}
                                for i, column_name in enumerate(sample_result.column_names):
                                    row_dict[column_name] = row[i] if i < len(row) else None
                                sample_data.append(row_dict)
                        
                        table_info["sample_data"] = sample_data
                        table_info["columns"] = sample_result.column_names if sample_result.column_names else []
                        
                    except Exception as e:
                        logger.warning(f"Could not get sample data for table {db_name}.{table_row[0]}: {e}")
                        table_info["sample_data"] = []
                        table_info["columns"] = []
                    
                    db_info["tables"].append(table_info)
                    db_info["total_rows"] += table_row[2] or 0
                    db_info["total_bytes"] += table_row[3] or 0
                
                db_info["table_count"] = len(db_info["tables"])
                summary["total_tables"] += db_info["table_count"]
                summary["total_rows"] += db_info["total_rows"]
                summary["total_size_bytes"] += db_info["total_bytes"]
                
            except Exception as e:
                logger.warning(f"Error getting tables for database {db_name}: {e}")
                db_info["error"] = f"Could not retrieve tables: {str(e)}"
            
            summary["databases"].append(db_info)
        
        print(f"✅ Generated summary with {len(summary['databases'])} databases and {summary['total_tables']} total tables")
        return json.dumps(summary, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error getting database summary: {e}")
        print(f"❌ Error getting database summary: {str(e)}")
        return f"❌ Error getting database summary: {str(e)}"


def main():
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()