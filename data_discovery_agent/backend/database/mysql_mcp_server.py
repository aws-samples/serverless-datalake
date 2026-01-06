"""
MySQL Database Tools for Strands Agents MCP Server
"""

import json
import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP
from database import db

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "sql-mcp-server",
    instructions="""
    # SQL MCP Server
    This server may access multiple databases and provide tools to access the data.
""",
    host="0.0.0.0",
    port=8000,
)


@mcp.tool()
async def test_mysql_connection() -> str:
    """
    Test the MySQL database connection.

    Returns:
        str: Connection status message
    """
    print("🔌 TEST_MYSQL_CONNECTION called")
    logger.info("TEST_MYSQL_CONNECTION called")
    try:
        if db.test_connection():
            print("✅ MySQL connection successful")
            return "✅ MySQL connection successful"
        else:
            print("❌ MySQL connection failed")
            return "❌ MySQL connection failed"
    except Exception as e:
        print(f"❌ MySQL connection error: {str(e)}")
        return f"❌ MySQL connection error: {str(e)}"


@mcp.tool()
async def list_mysql_schemas() -> str:
    """
    List all schemas/databases in the MySQL instance.

    Returns:
        str: JSON formatted list of schema names with details
    """
    print("📋 LIST_MYSQL_SCHEMAS called")
    logger.info("LIST_MYSQL_SCHEMAS called")
    try:
        schemas = db.list_schemas()
        result = json.dumps({"schemas": schemas, "count": len(schemas)}, indent=2)
        print(f"✅ Found {len(schemas)} schemas")
        return result
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        print(f"❌ Error listing schemas: {str(e)}")
        return f"❌ Error listing schemas: {str(e)}"


@mcp.tool()
async def list_mysql_tables(schema_name: Optional[str] = None) -> str:
    """
    List all tables in the MySQL database or a specific schema.

    Args:
        schema_name (str, optional): Name of the schema to list tables from

    Returns:
        str: JSON formatted list of table names
    """
    print(f"📋 LIST_MYSQL_TABLES called with schema: {schema_name}")
    logger.info(f"LIST_MYSQL_TABLES called with schema: {schema_name}")
    try:
        tables = db.list_tables(schema_name)    
        result = {"tables": tables, "count": len(tables)}
        for table_name in tables:
            if 'table_schemas' in result:
                result['table_schemas'].append({
                    "table_name": table_name,
                    "table_schema": db.get_table_schema(table_name, schema_name),
                    "database_schema_name": schema_name
                })
            else:
                result['table_schemas']=[{
                    "table_name": table_name,
                    "table_schema": db.get_table_schema(table_name, schema_name),
                    "database_schema_name": schema_name
                }]

        if schema_name:
            result["schema"] = schema_name
        print(f"✅ Found {len(tables)} tables in schema '{schema_name or 'default'}'")
        print(f'Table Schema {result}')

        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        print(f"❌ Error listing tables: {str(e)}")
        return f"❌ Error listing tables: {str(e)}"


@mcp.tool()
async def list_mysql_tables_by_schema() -> str:
    """
    List all tables grouped by schema/database.

    Returns:
        str: JSON formatted list of tables organized by schema
    """
    print("📋 LIST_MYSQL_TABLES_BY_SCHEMA called")
    logger.info("LIST_MYSQL_TABLES_BY_SCHEMA called")
    try:
        result = {}
        tables_by_schema = db.list_tables_by_schema()
        print(f'Table Schema {tables_by_schema}')

        for schema_name, tables in tables_by_schema.items():
            for table_name in tables:
                if 'table_schemas' in result:
                    result['table_schemas'].append({
                        "table_name": table_name,
                        "table_schema": db.get_table_schema(table_name, schema_name),
                        "database_schema_name": schema_name
                    })
                else:
                    result['table_schemas']=[{
                        "table_name": table_name,
                        "table_schema": db.get_table_schema(table_name, schema_name),
                        "database_schema_name": schema_name
                    }]
        total_tables = sum(len(tables) for tables in tables_by_schema.values())
        print(
            f"✅ Found {len(tables_by_schema)} schemas with {total_tables} total tables"
        )

        return json.dumps(
            {
                "schemas": tables_by_schema,
                "table_schemas": result['table_schemas'],
                "schema_count": len(tables_by_schema),
                "total_tables": total_tables,
            },
            indent=2,
        )
    except Exception as e:
        logger.error(f"Error listing tables by schema: {e}")
        print(f"❌ Error listing tables by schema: {str(e)}")
        return f"❌ Error listing tables by schema: {str(e)}"


@mcp.tool()
async def describe_mysql_table(
    table_name: str, schema_name: Optional[str] = None
) -> str:
    """
    Get detailed information about a specific MySQL table including schema, indexes, and metadata.

    Args:
        table_name (str): Name of the table to describe
        schema_name (str, optional): Schema name (defaults to configured database)

    Returns:
        str: JSON formatted table information
    """
    print(
        f"📊 DESCRIBE_MYSQL_TABLE called for table: {table_name}, schema: {schema_name}"
    )
    logger.info(
        f"DESCRIBE_MYSQL_TABLE called for table: {table_name}, schema: {schema_name}"
    )
    try:
        table_info = db.get_table_info(table_name, schema_name)
        if not table_info:
            print(
                f"❌ Table '{table_name}' not found in schema '{schema_name or db.config['database']}'"
            )
            return f"❌ Table '{table_name}' not found in schema '{schema_name or db.config['database']}'"

        print(f"✅ Retrieved table info for {table_name}")
        return json.dumps(table_info, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error describing table {table_name}: {e}")
        print(f"❌ Error describing table '{table_name}': {str(e)}")
        return f"❌ Error describing table '{table_name}': {str(e)}"


@mcp.tool()
async def execute_mysql_query(query: str, limit: Optional[int] = 100) -> str:
    """
    Execute a SELECT query against the MySQL database.

    Args:
        query (str): SQL SELECT query to execute
        limit (int, optional): Maximum number of rows to return (default: 100, max: 1000)

    Returns:
        str: JSON formatted query results
    """
    print(
        f"🔍 EXECUTE_MYSQL_QUERY called with query: {query[:100]}{'...' if len(query) > 100 else ''}, limit: {limit}"
    )
    logger.info(
        f"EXECUTE_MYSQL_QUERY called with query length: {len(query)}, limit: {limit}"
    )
    try:
        # Security check - only allow SELECT queries
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            print("❌ Only SELECT queries are allowed for security reasons")
            return "❌ Only SELECT queries are allowed for security reasons"

        # Apply limit if not already present
        if limit and "LIMIT" not in query_upper:
            # Ensure limit doesn't exceed maximum
            limit = min(limit, 1000)
            query = f"{query.rstrip(';')} LIMIT {limit}"

        results = db.execute_query(query)
        print(f"✅ Query executed successfully, returned {len(results)} rows")

        return json.dumps(
            {"query": query, "row_count": len(results), "results": results},
            indent=2,
            default=str,
        )

    except Exception as e:
        logger.error(f"Error executing query: {e}")
        print(f"❌ Query execution error: {str(e)}")
        return f"❌ Query execution error: {str(e)}"


@mcp.tool()
async def get_mysql_table_sample(
    schema_name: str, table_name: str, limit: int = 5
) -> str:
    """
    Get a sample of data from a MySQL table.

    Args:
        table_name (str): Name of the table to sample
        limit (int): Number of sample rows to return (default: 5, max: 50)

    Returns:
        str: JSON formatted sample data
    """
    print(
        f"📊 GET_MYSQL_TABLE_SAMPLE called for {schema_name}.{table_name}, limit: {limit}"
    )
    logger.info(
        f"GET_MYSQL_TABLE_SAMPLE called for {schema_name}.{table_name}, limit: {limit}"
    )
    try:
        # Ensure limit doesn't exceed maximum
        limit = min(limit, 50)

        query = f"SELECT * FROM `{schema_name}`.`{table_name}` LIMIT {limit}"
        results = db.execute_query(query)
        print(f"✅ Retrieved {len(results)} sample rows from {table_name}")

        return json.dumps(
            {"table": table_name, "sample_size": len(results), "data": results},
            indent=2,
            default=str,
        )

    except Exception as e:
        logger.error(f"Error getting table sample: {e}")
        print(f"❌ Error getting sample from table '{table_name}': {str(e)}")
        return f"❌ Error getting sample from table '{table_name}': {str(e)}"


@mcp.tool()
async def get_mysql_table_count(schema_name: str, table_name: str) -> str:
    """
    Get the row count for a MySQL table.

    Args:
        table_name (str): Name of the table to count

    Returns:
        str: JSON formatted count result
    """
    print(f"🔢 GET_MYSQL_TABLE_COUNT called for {schema_name}.{table_name}")
    logger.info(f"GET_MYSQL_TABLE_COUNT called for {schema_name}.{table_name}")
    try:
        query = f"SELECT COUNT(*) as row_count FROM `{schema_name}`.`{table_name}`"
        results = db.execute_query(query)
        row_count = results[0]["row_count"] if results else 0
        print(f"✅ Table {table_name} has {row_count} rows")

        return json.dumps(
            {
                "table": table_name,
                "row_count": row_count,
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error counting table rows: {e}")
        print(f"❌ Error counting rows in table '{table_name}': {str(e)}")
        return f"❌ Error counting rows in table '{table_name}': {str(e)}"


@mcp.tool()
async def get_mysql_schema_info(schema_name: str) -> str:
    """
    Get detailed information about a specific schema including all tables, their columns, and relationships.

    Args:
        schema_name (str): Name of the schema to analyze

    Returns:
        str: JSON formatted schema information
    """
    print(f"🏗️ GET_MYSQL_SCHEMA_INFO called for schema: {schema_name}")
    logger.info(f"GET_MYSQL_SCHEMA_INFO called for schema: {schema_name}")
    try:
        # Get schema basic info
        schema_info_query = """
        SELECT 
            SCHEMA_NAME as schema_name,
            DEFAULT_CHARACTER_SET_NAME as charset,
            DEFAULT_COLLATION_NAME as collation
        FROM INFORMATION_SCHEMA.SCHEMATA 
        WHERE SCHEMA_NAME = %s
        """
        schema_info = db.execute_query(schema_info_query, (schema_name,))

        if not schema_info:
            return f"❌ Schema '{schema_name}' not found"

        # Get all tables in schema
        tables = db.list_tables(schema_name)

        # Get detailed info for each table
        tables_detail = []
        for table_name in tables:
            table_info = db.get_table_info(table_name, schema_name)
            if table_info:
                # Get row count
                count_result = db.execute_query(
                    f"SELECT COUNT(*) as count FROM `{schema_name}`.`{table_name}`"
                )
                row_count = count_result[0]["count"] if count_result else 0

                tables_detail.append(
                    {
                        "name": table_name,
                        "row_count": row_count,
                        "columns": table_info["columns"],
                        "indexes": table_info["indexes"],
                        "foreign_keys": table_info["foreign_keys"],
                        "engine": table_info["table_info"]["ENGINE"],
                        "comment": table_info["table_info"]["TABLE_COMMENT"],
                    }
                )

        result = {
            "schema_info": schema_info[0],
            "table_count": len(tables),
            "tables": tables_detail,
        }

        print(f"✅ Retrieved schema info for {schema_name} with {len(tables)} tables")
        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting schema info: {e}")
        print(f"❌ Error getting schema info for '{schema_name}': {str(e)}")
        return f"❌ Error getting schema info for '{schema_name}': {str(e)}"


@mcp.tool()
async def search_mysql_table(
    schema_name: str, table_name: str, column: str, search_term: str, limit: int = 20
) -> str:
    """
    Search for records in a MySQL table where a column contains a specific term.

    Args:
        table_name (str): Name of the table to search
        column (str): Column name to search in
        search_term (str): Term to search for
        limit (int): Maximum number of results to return (default: 20, max: 100)

    Returns:
        str: JSON formatted search results
    """
    print(
        f"🔍 SEARCH_MYSQL_TABLE called for {schema_name}.{table_name}, column: {column}, term: {search_term}, limit: {limit}"
    )
    logger.info(
        f"SEARCH_MYSQL_TABLE called for {schema_name}.{table_name}, column: {column}, term: {search_term}, limit: {limit}"
    )
    try:
        # Ensure limit doesn't exceed maximum
        limit = min(limit, 100)

        query = f"SELECT * FROM `{schema_name}`.`{table_name}` WHERE `{column}` LIKE %s LIMIT {limit}"
        search_pattern = f"%{search_term}%"

        results = db.execute_query(query, (search_pattern,))
        print(f"✅ Search found {len(results)} matching records")

        return json.dumps(
            {
                "table": table_name,
                "column": column,
                "search_term": search_term,
                "result_count": len(results),
                "results": results,
            },
            indent=2,
            default=str,
        )

    except Exception as e:
        logger.error(f"Error searching table: {e}")
        print(f"❌ Error searching table '{table_name}': {str(e)}")
        return f"❌ Error searching table '{table_name}': {str(e)}"


@mcp.tool()
async def get_mysql_schema_relationships(schema_name: str) -> str:
    """
    Get all foreign key relationships within a schema to understand table dependencies.

    Args:
        schema_name (str): Name of the schema to analyze relationships

    Returns:
        str: JSON formatted relationship information
    """
    print(f"🔗 GET_MYSQL_SCHEMA_RELATIONSHIPS called for schema: {schema_name}")
    logger.info(f"GET_MYSQL_SCHEMA_RELATIONSHIPS called for schema: {schema_name}")
    try:
        # Get all foreign key relationships in the schema
        fk_query = """
        SELECT 
            kcu.TABLE_NAME as source_table,
            kcu.COLUMN_NAME as source_column,
            kcu.REFERENCED_TABLE_NAME as target_table,
            kcu.REFERENCED_COLUMN_NAME as target_column,
            kcu.CONSTRAINT_NAME as constraint_name,
            rc.UPDATE_RULE,
            rc.DELETE_RULE
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
        JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc 
            ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME 
            AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
        WHERE kcu.TABLE_SCHEMA = %s 
        AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY kcu.TABLE_NAME, kcu.CONSTRAINT_NAME
        """

        relationships = db.execute_query(fk_query, (schema_name,))

        # Organize relationships by table
        tables_with_fks = {}
        for rel in relationships:
            source_table = rel["source_table"]
            if source_table not in tables_with_fks:
                tables_with_fks[source_table] = []

            tables_with_fks[source_table].append(
                {
                    "constraint_name": rel["constraint_name"],
                    "source_column": rel["source_column"],
                    "references": {
                        "table": rel["target_table"],
                        "column": rel["target_column"],
                    },
                    "update_rule": rel["UPDATE_RULE"],
                    "delete_rule": rel["DELETE_RULE"],
                }
            )

        result = {
            "schema": schema_name,
            "relationship_count": len(relationships),
            "tables_with_foreign_keys": len(tables_with_fks),
            "relationships": tables_with_fks,
        }

        print(
            f"✅ Found {len(relationships)} relationships in {len(tables_with_fks)} tables"
        )
        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting schema relationships: {e}")
        print(f"❌ Error getting relationships for schema '{schema_name}': {str(e)}")
        return f"❌ Error getting relationships for schema '{schema_name}': {str(e)}"


@mcp.tool()
async def debug_mysql_schema_query() -> str:
    """
    Debug tool to troubleshoot schema listing issues by running various diagnostic queries.
    
    Returns:
        str: JSON formatted debug information
    """
    print("🔧 DEBUG_MYSQL_SCHEMA_QUERY called")
    logger.info("DEBUG_MYSQL_SCHEMA_QUERY called")
    try:
        debug_info = {}
        
        # Test 1: Basic connection info
        debug_info["connection_config"] = {
            "host": db.config.get('host'),
            "port": db.config.get('port'),
            "user": db.config.get('user'),
            "database": db.config.get('database')
        }
        
        # Test 2: Current database
        current_db_query = "SELECT DATABASE() as current_database"
        current_db = db.execute_query(current_db_query)
        debug_info["current_database"] = current_db
        
        # Test 3: All schemas (no filtering)
        all_schemas_query = "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA ORDER BY SCHEMA_NAME"
        all_schemas = db.execute_query(all_schemas_query)
        debug_info["all_schemas"] = all_schemas
        
        # Test 4: User schemas (filtered)
        user_schemas_query = """
        SELECT SCHEMA_NAME 
        FROM INFORMATION_SCHEMA.SCHEMATA 
        WHERE SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
        ORDER BY SCHEMA_NAME
        """
        user_schemas = db.execute_query(user_schemas_query)
        debug_info["user_schemas"] = user_schemas
        
        # Test 5: All tables (no filtering)
        all_tables_query = """
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE 
        FROM INFORMATION_SCHEMA.TABLES 
        ORDER BY TABLE_SCHEMA, TABLE_NAME 
        LIMIT 20
        """
        all_tables = db.execute_query(all_tables_query)
        debug_info["sample_tables"] = all_tables
        
        # Test 6: Base tables only
        base_tables_query = """
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME 
        LIMIT 20
        """
        base_tables = db.execute_query(base_tables_query)
        debug_info["sample_base_tables"] = base_tables
        
        # Test 7: User base tables (filtered)
        user_base_tables_query = """
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
        AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        user_base_tables = db.execute_query(user_base_tables_query)
        debug_info["user_base_tables"] = user_base_tables
        
        # Test 8: Check privileges
        privileges_query = "SHOW GRANTS FOR CURRENT_USER()"
        try:
            privileges = db.execute_query(privileges_query)
            debug_info["user_privileges"] = privileges
        except Exception as e:
            debug_info["user_privileges_error"] = str(e)
        
        print(f"✅ Debug query completed, found {len(user_base_tables)} user base tables")
        return json.dumps(debug_info, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in debug query: {e}")
        print(f"❌ Error in debug query: {str(e)}")
        return f"❌ Error in debug query: {str(e)}"

@mcp.tool()
async def get_mysql_database_summary() -> str:
    """
    Gets the table schemas, sample data per table and summary of the MySQL database including all tables and their basic information.

    Returns:
        str: JSON formatted database summary
    """
    print("📋 GET_MYSQL_DATABASE_SUMMARY called")
    logger.info("GET_MYSQL_DATABASE_SUMMARY called")
    try:
        schemas_with_tables = db.list_tables_by_schema()
        total_tables = sum(len(tables) for tables in schemas_with_tables.values())

        summary = {
            "database": db.config["database"],
            "host": db.config["host"],
            "port": db.config["port"],
            "schema_count": len(schemas_with_tables),
            "schemas": list(schemas_with_tables.keys()),
            "total_tables": total_tables,
            "schemas_detail": {},
        }

        # Process each schema
        for schema_name, table_names in schemas_with_tables.items():
            schema_detail = {
                "name": schema_name,
                "table_count": len(table_names),
                "tables": [],
            }

            for table_name in table_names:
                try:
                    # Get comprehensive table info including schema and indexes
                    table_info = db.get_table_info(table_name, schema_name)
                    if not table_info:
                        schema_detail["tables"].append(
                            {
                                "name": table_name,
                                "schema": schema_name,
                                "error": "Table not found or no information available",
                            }
                        )
                        continue

                    # Get row count
                    count_result = db.execute_query(
                        f"SELECT COUNT(*) as count FROM `{schema_name}`.`{table_name}`"
                    )
                    row_count = count_result[0]["count"] if count_result else 0

                    # Get sample data
                    sample_query = (
                        f"SELECT * FROM `{schema_name}`.`{table_name}` LIMIT 3"
                    )
                    sample_results = db.execute_query(sample_query)

                    schema_detail["tables"].append(
                        {
                            "name": table_name,
                            "schema": schema_name,
                            "row_count": row_count,
                            "table_info": table_info["table_info"],
                            "columns": table_info["columns"],
                            "indexes": table_info["indexes"],
                            "sample_data": sample_results,
                        }
                    )
                except Exception as table_error:
                    logger.warning(
                        f"Error getting info for table {schema_name}.{table_name}: {table_error}"
                    )
                    schema_detail["tables"].append(
                        {
                            "name": table_name,
                            "schema": schema_name,
                            "error": str(table_error),
                        }
                    )

            summary["schemas_detail"][schema_name] = schema_detail

        print(
            f"✅ Generated database summary with {len(schemas_with_tables)} schemas and {total_tables} total tables"
        )
        return json.dumps(summary, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error getting database summary: {e}")
        print(f"❌ Error getting database summary: {str(e)}")
        return f"❌ Error getting database summary: {str(e)}"


def main():
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
