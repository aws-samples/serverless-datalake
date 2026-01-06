#!/usr/bin/env python3
"""
Startup script for the Athena MCP Server
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
        from database.athena_mcp import main
        print("🚀 Starting Athena MCP Server on http://localhost:8001/sse")
        main()
    except Exception as e:
        print(f"❌ Failed to start Athena MCP Server: {e}")
        sys.exit(1)