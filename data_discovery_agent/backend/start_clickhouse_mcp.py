#!/usr/bin/env python3
"""
Startup script for the ClickHouse MCP Server
"""

import sys
import os
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    try:
        from database.clickhouse_mcp import main
        print("🚀 Starting ClickHouse MCP Server on http://localhost:8002/sse")
        print("📊 ClickHouse connection: localhost:8123")
        print("🔧 Make sure ClickHouse is running and accessible")
        main()
    except Exception as e:
        print(f"❌ Failed to start ClickHouse MCP Server: {e}")
        sys.exit(1)