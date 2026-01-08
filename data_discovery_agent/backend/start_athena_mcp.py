#!/usr/bin/env python3
"""
Startup script for the Athena MCP Server
"""

import sys
import os
import logging
import logging.config

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Get logging level from environment variable or default to INFO
log_level = os.environ.get('PYTHONLOG', 'INFO')

# Configure logging with both console and file handlers
logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': log_level,
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'level': log_level,
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': 'logs/athena_mcp.log',
            'mode': 'a',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': log_level,
            'propagate': False
        },
        'fastmcp': {
            'handlers': ['console', 'file'],
            'level': log_level,
            'propagate': False,
        },
        'mcp': {
            'handlers': ['console', 'file'],
            'level': log_level,
            'propagate': False,
        },
        'uvicorn': {
            'handlers': ['console', 'file'],
            'level': log_level,
            'propagate': False,
        },
    }
}

logging.config.dictConfig(logging_config)

if __name__ == "__main__":
    try:
        from database.mcp.athena_mcp import main
        print("🚀 Starting Athena MCP Server on http://localhost:8001/sse")
        print(f"📝 Logs will be written to: {os.path.abspath('logs/athena_mcp.log')}")
        print(f"📊 Logging level: {log_level}")
        
        # Get a logger for this module
        logger = logging.getLogger(__name__)
        logger.info("Starting Athena MCP Server")
        logger.info(f"Logging level set to: {log_level}")
        logger.info(f"Log file: {os.path.abspath('logs/athena_mcp.log')}")
        
        main()
    except Exception as e:
        print(f"❌ Failed to start Athena MCP Server: {e}")
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to start Athena MCP Server: {e}")
        sys.exit(1)