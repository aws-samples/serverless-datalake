#!/usr/bin/env python3
"""
Flask API for MCP Dashboard Chatbot
Provides REST endpoints and SSE streaming for the React frontend to interact with MCP servers.
"""

from flask import Flask, request, jsonify, Response, stream_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit, disconnect
import asyncio
import json
import logging
from datetime import datetime
import sys
import os
import pathlib

# Import from reorganized modules
from database.database_mcp_clients import MCPClientChatbot
from config.chatbot_config import ChatbotConfig, ModelConfig, SessionConfig, ProcessingConfig, DashboardConfig
import threading
import queue
import time
# Configure logging
import logging.config
import os

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Get logging level from environment variable or default to ERROR
log_level = os.environ.get('PYTHONLOG', 'ERROR')

# Configure logging with more control
logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': log_level,
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': log_level,
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': 'logs/backend.log',
            'mode': 'a',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default', 'file'],
            'level': log_level,
            'propagate': True
        },
        'socketio': {
            'handlers': ['default', 'file'],
            'level': 'ERROR',  # Always keep socketio at ERROR level
            'propagate': False,
        },
        'engineio': {
            'handlers': ['default', 'file'],
            'level': 'ERROR',  # Always keep engineio at ERROR level
            'propagate': False,
        },
        'werkzeug': {
            'handlers': ['default', 'file'],
            'level': log_level,
            'propagate': False,
        },
    }
}

logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins="*")
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)
# Initialize SocketIO with CORS support
# socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')


# Global chatbot template and per-connection instances
chatbot_template = None
chatbot_instances = {}
chatbot_lock = threading.Lock()
sse_urls_global = None
config_global = None


def start_chatbot():
    """Initialize the chatbot template and global configuration."""
    global chatbot_template, sse_urls_global, config_global

    def run_chatbot():
        global chatbot_template, sse_urls_global, config_global
        sse_urls = []
        try:
            logger.info("Starting MCP chatbot template initialization")
            
            # Load configuration
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'chatbot_config.json')
            if os.path.exists(config_path):
                logger.info(f"Loading configuration from {config_path}")
                config_global = ChatbotConfig.from_file(config_path)
            else:
                logger.info("Using default configuration")
                config_global = ChatbotConfig()
            
            # Load MCP server details from JSON file
            try:
                possible_paths = [
                    'mcp_servers.json',  # Current directory
                    os.path.join(os.path.dirname(__file__), 'mcp_servers.json'),  # Same dir as script
                    os.path.join(os.getcwd(), 'mcp_servers.json'),  # Current working directory
                ]
                
                config_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        config_path = path
                        break
                if not config_path:
                    logger.error(f"mcp_servers.json not found in any of these locations: {possible_paths}")
                    logger.error(f"Current working directory: {os.getcwd()}")
                    logger.error(f"Script directory: {os.path.dirname(__file__)}")
                    raise FileNotFoundError("mcp_servers.json not found")
                
                with open(config_path, 'r') as f:
                    mcp_config = json.load(f)
                    sse_urls_global = mcp_config.get('servers', [])
                logger.info(f"Loaded {len(sse_urls_global)} MCP servers from configuration file")
            except Exception as e:
                logger.error(f"Failed to load MCP servers from config file: {e}")
                logger.error("No MCP servers configured, chatbot will not be initialized")
                sys.exit(0)
                
            # Create a template chatbot instance to validate configuration
            logger.info("Creating MCPClientChatbot template with configuration")
            chatbot_template = MCPClientChatbot(sse_urls=sse_urls_global, config=config_global)
            
            # Start the template chatbot to validate MCP connections
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.info("Starting chatbot template initialization")
            loop.run_until_complete(chatbot_template.start())
            logger.info("Chatbot template initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to start chatbot template: {e}")
            logger.error(f"Error details: {str(e)}")
            logger.info("Running in demo mode without MCP servers")
            chatbot_template = None

    # Start chatbot template initialization in a separate thread
    thread = threading.Thread(target=run_chatbot, daemon=True)
    thread.start()
    
    # Give the thread a moment to initialize
    time.sleep(1)
    
    # Check if chatbot template was initialized successfully
    with chatbot_lock:
        if chatbot_template is None:
            logger.error("Chatbot template failed to initialize")
        else:
            logger.info("Chatbot template thread started successfully")

def create_chatbot_for_connection(client_id):
    """Create a new chatbot instance for a specific connection."""
    global chatbot_template, sse_urls_global, config_global, chatbot_instances
    
    try:
        if not chatbot_template or not sse_urls_global or not config_global:
            raise Exception("Chatbot template not initialized")
            
        logger.info(f"Creating new chatbot instance for connection {client_id}")
        
        # Create a new chatbot instance for this connection
        new_chatbot = MCPClientChatbot(sse_urls=sse_urls_global, config=config_global)
        
        # Initialize the new chatbot instance
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(new_chatbot.start())
            logger.info(f"Chatbot instance initialized for connection {client_id}")
        finally:
            loop.close()
        
        # Store the instance
        with chatbot_lock:
            chatbot_instances[client_id] = new_chatbot
            
        return new_chatbot
        
    except Exception as e:
        logger.error(f"Failed to create chatbot instance for connection {client_id}: {e}")
        return None

def get_chatbot_for_connection(client_id):
    """Get the chatbot instance for a specific connection."""
    with chatbot_lock:
        return chatbot_instances.get(client_id)

def refresh_all_orchestrator_agents():
    """Refresh orchestrator agents across all active chatbot instances."""
    refreshed_count = 0
    failed_count = 0
    
    with chatbot_lock:
        for client_id, chatbot_instance in chatbot_instances.items():
            try:
                chatbot_instance.refresh_orchestrator_agent()
                refreshed_count += 1
                logger.info(f"Refreshed orchestrator agent for chatbot instance {client_id}")
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to refresh orchestrator agent for chatbot instance {client_id}: {e}")
    
    logger.info(f"Orchestrator agent refresh completed: {refreshed_count} successful, {failed_count} failed")
    return {"refreshed": refreshed_count, "failed": failed_count}

def cleanup_chatbot_for_connection(client_id):
    """Clean up the chatbot instance for a specific connection."""
    with chatbot_lock:
        if client_id in chatbot_instances:
            try:
                chatbot_instances[client_id].destroy_all_agents(session_id=client_id)
                del chatbot_instances[client_id]
                logger.info(f"Cleaned up chatbot instance for connection {client_id}")
            except Exception as e:
                logger.error(f"Error cleaning up chatbot instance for connection {client_id}: {e}")

@app.route("/api/dashboard/<filename>", methods=["GET"])
def serve_dashboard(filename):
    """Serve generated dashboard HTML files."""
    try:
        # Use pathlib for relative path
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent
        dashboard_path = project_root / "generated_dashboards" / filename
        if dashboard_path.exists():
            with open(dashboard_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return html_content, 200, {"Content-Type": "text/html"}
        else:
            return jsonify({"error": "Dashboard not found"}), 404
    except Exception as e:
        logger.error(f"Error serving dashboard: {e}")
        return jsonify({"error": "Failed to serve dashboard"}), 500

@app.route("/api/dashboards/history", methods=["GET"])
def get_dashboard_history():
    """Get list of all generated dashboards."""
    try:
        # Use pathlib for relative path
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent
        dashboard_dir = project_root / "generated_dashboards"
        if not dashboard_dir.exists():
            return jsonify({"dashboards": []})

        dashboards = []
        for file_path in dashboard_dir.glob("*.html"):
            stat = file_path.stat()
            dashboards.append(
                {
                    "filename": file_path.name,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "size": stat.st_size,
                }
            )

        # Sort by creation date, newest first
        dashboards.sort(key=lambda x: x["created_at"], reverse=True)
        return jsonify({"dashboards": dashboards})

    except Exception as e:
        logger.error(f"Error getting dashboard history: {e}")
        return jsonify({"error": "Failed to get dashboard history"}), 500


@app.route("/api/reports/history", methods=["GET"])
def get_report_history():
    """Get list of all generated reports."""
    try:
        # Use pathlib for relative path
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent
        dashboard_dir = project_root / "generated_reports"
        if not dashboard_dir.exists():
            return jsonify({"reports": []})

        dashboards = []
        for file_path in dashboard_dir.glob("*.html"):
            stat = file_path.stat()
            dashboards.append(
                {
                    "filename": file_path.name,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "size": stat.st_size,
                }
            )

        # Sort by creation date, newest first
        dashboards.sort(key=lambda x: x["created_at"], reverse=True)
        return jsonify({"reports": dashboards})

    except Exception as e:
        logger.error(f"Error getting report history: {e}")
        return jsonify({"error": "Failed to get report history"}), 500


@app.route("/api/report/<filename>", methods=["GET"])
def serve_report(filename):
    """Serve generated report HTML files."""
    try:
        # Use pathlib for relative path
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent
        dashboard_path = project_root / "generated_reports" / filename
        if dashboard_path.exists():
            with open(dashboard_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return html_content, 200, {"Content-Type": "text/html"}
        else:
            return jsonify({"error": "Report not found"}), 404
    except Exception as e:
        logger.error(f"Error serving report: {e}")
        return jsonify({"error": "Failed to serve report"}), 500


@app.route("/api/widget/<filename>", methods=["GET"])
def serve_widget(filename):
    """Serve generated widget HTML files."""
    try:
        # Use pathlib for relative path
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent
        widget_path = project_root / "generated_widgets" / filename
        if widget_path.exists():
            with open(widget_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return html_content, 200, {"Content-Type": "text/html"}
        else:
            return jsonify({"error": "Widget not found"}), 404
    except Exception as e:
        logger.error(f"Error serving dashboard: {e}")
        return jsonify({"error": "Failed to serve dashboard"}), 500

@app.route("/api/widget/history", methods=["GET"])
def get_widget_history():
    """Get list of all generated widgets."""
    try:
        # Use pathlib for relative path
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent
        widget_dir = project_root / "generated_widgets"
        if not widget_dir.exists():
            return jsonify({"widgets": []})

        widgets = []
        for file_path in widget_dir.glob("*.html"):
            stat = file_path.stat()
            widgets.append(
                {
                    "filename": file_path.name,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "size": stat.st_size,
                }
            )

        # Sort by creation date, newest first
        widgets.sort(key=lambda x: x["created_at"], reverse=True)
        return jsonify({"widgets": widgets, "dashboards": widgets})

    except Exception as e:
        logger.error(f"Error getting widget history: {e}")
        return jsonify({"error": "Failed to get widget history"}), 500



@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current chatbot configuration."""
    try:
        if config_global:
            return jsonify({
                "model": {
                    "primary_model_id": config_global.model.primary_model_id,
                    "cheaper_model_id": config_global.model.cheaper_model_id,
                    "max_tokens": config_global.model.max_tokens,
                    "temperature": config_global.model.temperature
                },
                "session": {
                    "session_timeout_minutes": config_global.session.session_timeout_minutes,
                    "max_conversation_length": config_global.session.max_conversation_length,
                    "enable_summarization": config_global.session.enable_summarization,
                    "summarization_threshold": config_global.session.summarization_threshold
                },
                "processing": {
                    "max_iterations": config_global.processing.max_iterations,
                    "require_human_confirmation": config_global.processing.require_human_confirmation,
                    "enable_parallel_execution": config_global.processing.enable_parallel_execution,
                    "timeout_seconds": config_global.processing.timeout_seconds
                },
                "dashboard": {
                    "output_directory": config_global.dashboard.output_directory,
                    "enable_export": config_global.dashboard.enable_export,
                    "default_chart_library": config_global.dashboard.default_chart_library,
                    "max_datasets": config_global.dashboard.max_datasets
                },
                "log_level": config_global.log_level,
                "debug_mode": config_global.debug_mode
            })
        else:
            return jsonify({"error": "Chatbot not initialized"}), 500
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"error": "Failed to get configuration"}), 500

@app.route("/api/config", methods=["POST"])
def update_config():
    """Update chatbot configuration."""
    global config_global
    
    try:
        if not config_global:
            return jsonify({"error": "Chatbot not initialized"}), 500
            
        config_data = request.get_json()
        if not config_data:
            return jsonify({"error": "No configuration data provided"}), 400
            
        # Create new config from the provided data
        new_config = ChatbotConfig(
            model=ModelConfig(**config_data.get('model', {})),
            session=SessionConfig(**config_data.get('session', {})),
            processing=ProcessingConfig(**config_data.get('processing', {})),
            dashboard=DashboardConfig(**config_data.get('dashboard', {})),
            log_level=config_data.get('log_level', 'INFO'),
            debug_mode=config_data.get('debug_mode', False)
        )
        
        # Update the global configuration
        config_global = new_config
        
        # Update all existing chatbot instances
        with chatbot_lock:
            for client_id, chatbot_instance in chatbot_instances.items():
                try:
                    chatbot_instance.update_config(new_config)
                    logger.info(f"Updated config for chatbot instance {client_id}")
                except Exception as e:
                    logger.error(f"Failed to update config for chatbot instance {client_id}: {e}")
        
        return jsonify({"message": "Configuration updated successfully"})
        
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"error": f"Failed to update configuration: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for container health monitoring."""
    try:
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "mcp-data-detective-backend"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/api/mcp-status", methods=["GET"])
def get_mcp_status():
    """Get MCP server connection status."""
    try:
        if not chatbot_template:
            return jsonify({"error": "Chatbot not initialized"}), 500
            
        # Get detailed connection status for initialized clients
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            connection_status = loop.run_until_complete(chatbot_template.get_connection_status())
        finally:
            loop.close()
            
        servers = {}
        
        # First, add all configured servers from the original configuration
        for server_key, server_config in sse_urls_global.items():
            server_name = server_config.get("name", str(server_key).capitalize())
            servers[server_key] = {  # Use server_key as the consistent identifier
                "name": server_name,
                "status": "not_initialized",  # Default status
                "mcp_url": server_config.get("url", ""),
                "mcp_command": server_config.get("command", ""),
                "mcp_args": server_config.get("args", ""),
                "reconnection_attempts": 0,
                "max_attempts_reached": False,
                "disabled": server_config.get("disabled", False),
                "transport_type": server_config.get("transportType", "stdio"),
                "description": server_config.get("description", "")
            }
        
        # Then, update with actual status for initialized clients
        for key, value in chatbot_template.mcp_clients.items():
            status_info = connection_status.get(key, {})
            if key in servers:  # Update existing entry
                servers[key].update({
                    "status": "connected" if status_info.get("connected", False) else "disconnected",
                    "reconnection_attempts": status_info.get("reconnection_attempts", 0),
                    "max_attempts_reached": status_info.get("max_attempts_reached", False),
                    "disabled": False,  # If it's in mcp_clients, it's not disabled
                })
            else:  # This shouldn't happen, but handle it gracefully
                servers[key] = {
                    "name": value.get("name", key),
                    "status": "connected" if status_info.get("connected", False) else "disconnected",
                    "mcp_url": value.get("mcp_url", ""),
                    "mcp_command": value.get("mcp_command", ""),
                    "mcp_args": value.get("mcp_args", ""),
                    "reconnection_attempts": status_info.get("reconnection_attempts", 0),
                    "max_attempts_reached": status_info.get("max_attempts_reached", False),
                    "disabled": False,
                    "transport_type": value.get("transportType", "stdio"),
                    "description": value.get("description", "")
                }
            
        return jsonify({
            "timestamp": datetime.now().isoformat(), 
            "servers": servers,
            "health_check_enabled": True,
            "total_configured": len(sse_urls_global),
            "total_initialized": len(chatbot_template.mcp_clients),
            "active_connections": len(chatbot_instances)
        })

    except Exception as e:
        logger.error(f"MCP status check failed: {e}")
        return (
            jsonify({"error": "Failed to check MCP server status", "details": str(e)}),
            500,
        )

@app.route("/api/mcp-reconnect", methods=["POST"])
def force_mcp_reconnect():
    """Force reconnection of MCP servers."""
    try:
        if not chatbot_template:
            return jsonify({"error": "Chatbot not initialized"}), 500
            
        data = request.get_json() or {}
        mcp_name = data.get("mcp_name")
        
        def reconnect_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if mcp_name:
                    # Check if server is initialized
                    if mcp_name in chatbot_template.mcp_clients:
                        # Reconnect existing client
                        success = loop.run_until_complete(chatbot_template.force_reconnect_client(mcp_name))
                        return {"mcp_name": mcp_name, "success": success, "action": "reconnected"}
                    else:
                        # Try to initialize uninitialized server
                        success = loop.run_until_complete(chatbot_template.retry_failed_initialization(mcp_name))
                        return {"mcp_name": mcp_name, "success": success, "action": "initialized"}
                else:
                    # Reconnect all existing clients
                    loop.run_until_complete(chatbot_template.force_reconnect_all())
                    
                    # Try to initialize any failed servers
                    for server_key in sse_urls_global.keys():
                        if server_key not in chatbot_template.mcp_clients:
                            logger.info(f"Attempting to initialize previously failed server: {server_key}")
                            loop.run_until_complete(chatbot_template.retry_failed_initialization(server_key))
                    
                    return {"message": "Reconnection and initialization attempted for all MCP servers"}
            finally:
                loop.close()
        
        result = reconnect_task()
        
        # Also update all active chatbot instances
        with chatbot_lock:
            for client_id, chatbot_instance in chatbot_instances.items():
                try:
                    def update_instance():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            if mcp_name:
                                loop.run_until_complete(chatbot_instance.force_reconnect_client(mcp_name))
                            else:
                                loop.run_until_complete(chatbot_instance.force_reconnect_all())
                        finally:
                            loop.close()
                    
                    update_instance()
                    logger.info(f"Updated MCP connections for chatbot instance {client_id}")
                except Exception as e:
                    logger.error(f"Failed to update MCP connections for chatbot instance {client_id}: {e}")
        
        return jsonify({
            "message": "Reconnection completed",
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"MCP reconnection failed: {e}")
        return jsonify({
            "error": "Failed to reconnect MCP servers", 
            "details": str(e)
        }), 500


@app.route("/api/refresh-orchestrators", methods=["POST"])
def refresh_orchestrators():
    """Manually refresh orchestrator agents across all active connections."""
    try:
        result = refresh_all_orchestrator_agents()
        
        return jsonify({
            "message": "Orchestrator agents refresh completed",
            "refreshed_instances": result["refreshed"],
            "failed_instances": result["failed"],
            "total_instances": len(chatbot_instances),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to refresh orchestrator agents: {e}")
        return jsonify({
            "error": "Failed to refresh orchestrator agents", 
            "details": str(e)
        }), 500


# socket event handlers
@socketio.on("connect")
def handle_connect():
    """Handle WebSocket connection."""
    try:
        client_id = request.sid
        logger.info(f"Client connecting: Socket ID {client_id}")
        
        # Check if chatbot template exists
        if not chatbot_template:
            logger.error("Chatbot template not initialized when handling connection")
            emit(
                "connected",
                {
                    "status": "error",
                    "error": "Chat system is not available. Please try again later.",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return
            
        # Initialize the conversation manager in a separate thread to avoid blocking
        def initialize_conversation():
            try:
                logger.info(f"Creating chatbot instance for session {client_id}")
                
                # Create a new chatbot instance for this connection
                chatbot_instance = create_chatbot_for_connection(client_id)
                
                if not chatbot_instance:
                    raise Exception("Failed to create chatbot instance")

                # Create agents for this session
                try:
                    chatbot_instance.create_all_agents(user_id=client_id, session_id=client_id)
                    
                    # Verify that the orchestrator agent was created
                    if not chatbot_instance.orchestrate_agent:
                        raise Exception("Orchestrator agent was not created properly")
                        
                    logger.info(f"Agents created successfully for session {client_id}")
                    
                    # Emit connection success with session info
                    socketio.emit(
                        "connected",
                        {
                            "status": "connected",
                            "sid": client_id,
                            "timestamp": datetime.now().isoformat()
                        },
                        room=client_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to create agents for session {client_id}: {e}")
                    socketio.emit(
                        "connected",
                        {
                            "status": "error",
                            "sid": client_id,
                            "error": f"Failed to initialize chat system: {str(e)}",
                            "timestamp": datetime.now().isoformat(),
                        },
                        room=client_id,
                    )

            except Exception as e:
                logger.error(
                    f"Error initializing conversation for session {client_id}: {e}"
                )
                socketio.emit(
                    "connected",
                    {
                        "status": "error",
                        "sid": client_id,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=client_id,
                )

        # Start initialization in background thread
        init_thread = threading.Thread(target=initialize_conversation, daemon=True)
        init_thread.start()

        logger.info(f"Client connection handler started for: {client_id}")

    except Exception as e:
        logger.error(f"Error in WebSocket connect handler: {e}")
        emit(
            "connected",
            {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )

@socketio.on("disconnect")
def handle_disconnect():
    """Handle WebSocket disconnection and preserve conversation state."""
    try:
        client_id = request.sid
        
        emit("disconnected",
            {
                "status": "disconnected",
                "sid": client_id,
                "timestamp": datetime.now().isoformat(),
            }
            )
        
        # Clean up the chatbot instance for this connection
        cleanup_chatbot_for_connection(client_id)
        
    except Exception as e:
        logger.error(f"Error in WebSocket disconnect handler: {e}")

@socketio.on("ping")
def handle_ping():
    """Handle ping for connection testing."""
    emit("pong", {"timestamp": datetime.now().isoformat()})

@socketio.on("chat_message")
def handle_chat_message(data):
    """Handle chat messages through WebSocket with conversation state."""
    try:
        client_sid = request.sid
        
        # Get the chatbot instance for this connection
        chatbot_instance = get_chatbot_for_connection(client_sid)
        
        # Check if chatbot instance exists
        if not chatbot_instance:
            logger.error(f"Chatbot instance not found for connection {client_sid}")
            emit(
                "chat_response",
                {
                    "type": "error",
                    "content": "Chat system is not available. Please try reconnecting.",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return
            
        # Check if orchestrator agent exists and create if needed
        if not chatbot_instance.orchestrate_agent:
            logger.warning(f"Orchestrator agent not found for connection {client_sid}, creating agents")
            try:
                chatbot_instance.create_all_agents(user_id=client_sid, session_id=client_sid)
                if not chatbot_instance.orchestrate_agent:
                    raise Exception("Failed to create orchestrator agent")
            except Exception as e:
                logger.error(f"Failed to create agents for connection {client_sid}: {e}")
                emit(
                    "chat_response",
                    {
                        "type": "error",
                        "content": "Failed to initialize chat system. Please try again later.",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                return
                
        message = data.get("message", "").strip()
        

        if not message:
            emit(
                "chat_response",
                {
                    "type": "error",
                    "content": "Message is required",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return

        # Define streaming callback for WebSocket
        async def stream_callback(data):
            """Callback function to stream responses."""
            try:
                socketio.emit(
                    "chat_response",
                    {**data, "timestamp": datetime.now().isoformat()},
                    room=client_sid,
                )
            except Exception as e:
                logger.error(f"Error in stream callback: {e}")

        # Process message in a separate thread
        def process_message():
            try:
                # Create a new event loop for the thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Process message with conversation manager
                loop.run_until_complete(
                    chatbot_instance.process_message_stream(message, stream_callback, user_id=client_sid, session_id=client_sid)
                )
            except Exception as e:
                logger.error(f"Error processing message for connection {client_sid}: {e}")
                socketio.emit(
                    "chat_response",
                    {
                        "type": "error",
                        "content": f"Processing error: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=client_sid,
                )
            finally:
                loop.close()

        # Start processing in background thread
        process_thread = threading.Thread(target=process_message, daemon=True)
        process_thread.start()

        # Send immediate acknowledgment
        emit(
            "chat_response",
            {
                "type": "status",
                "content": "Processing message...",
                "timestamp": datetime.now().isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error in chat_message handler for connection {client_sid}: {e}")
        emit(
            "chat_response",
            {
                "type": "error",
                "content": f"Error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            },
        )

@socketio.on("confirm_plan")
def handle_confirm_plan(data):
    """
    Handle plan confirmation from client.
    
    Args:
        data: Dictionary containing the plan and original query
    """
    try:
        client_sid = request.sid
        
        # Get the chatbot instance for this connection
        chatbot_instance = get_chatbot_for_connection(client_sid)
        
        if not chatbot_instance:
            logger.error(f"Chatbot instance not found for connection {client_sid}")
            emit('chat_response', {
                'type': 'error',
                'content': "Chat system is not available. Please try reconnecting.",
                'timestamp': datetime.now().isoformat()
            })
            return
        
        # Define streaming callback for WebSocket
        async def stream_callback(update_data):
            """Callback function to stream responses."""
            try:
                socketio.emit(
                    "chat_response",
                    {**update_data, "timestamp": datetime.now().isoformat()},
                    room=client_sid,
                )
            except Exception as e:
                logger.error(f"Error in stream callback: {e}")
        
        def handle_confirmation():
            try:
                # Create a new event loop for the thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                is_single_widget = data.get("is_single_widget", False)
                # Process message with conversation manager
                loop.run_until_complete(
                    chatbot_instance.continue_with_confirmed_plan(
                        plan=data.get('plan', []),
                        original_query=data.get('original_query', ''),
                        is_single_widget=is_single_widget,
                        stream_callback=stream_callback,
                        user_id=client_sid,
                        session_id=client_sid
                    )
                )
            except Exception as e:
                logger.error(f"Error processing plan confirmation for connection {client_sid}: {e}")
                socketio.emit(
                    'chat_response',
                    {
                        'type': 'error',
                        'content': f"An error occurred while executing the plan: {str(e)}",
                        'timestamp': datetime.now().isoformat()
                    },
                    room=client_sid
                )
            finally:
                loop.close()
        
        # Start processing in background thread
        process_thread = threading.Thread(target=handle_confirmation, daemon=True)
        process_thread.start()
        
        # Send immediate acknowledgment
        emit(
            "chat_response",
            {
                "type": "status",
                "content": "Processing plan confirmation...",
                "timestamp": datetime.now().isoformat(),
            },
        )
        
    except Exception as e:
        logger.error(f"Error processing plan confirmation: {e}")
        emit('chat_response', {
            'type': 'error',
            'content': f"An error occurred while executing the plan: {str(e)}",
            'timestamp': datetime.now().isoformat()
        })

@socketio.on("tool_approval_response")
def handle_tool_approval_response(data):
    """
    Handle tool approval response from client.
    
    Args:
        data: Dictionary containing approval response details
    """
    try:
        client_sid = request.sid
        
        # Get the chatbot instance for this connection
        chatbot_instance = get_chatbot_for_connection(client_sid)
        
        if not chatbot_instance:
            logger.error(f"Chatbot instance not found for connection {client_sid}")
            emit('chat_response', {
                'type': 'error',
                'content': "Chat system is not available. Please try reconnecting.",
                'timestamp': datetime.now().isoformat()
            })
            return
        
        # Define streaming callback for WebSocket
        async def stream_callback(update_data):
            """Callback function to stream responses."""
            try:
                socketio.emit(
                    "chat_response",
                    {**update_data, "timestamp": datetime.now().isoformat()},
                    room=client_sid,
                )
            except Exception as e:
                logger.error(f"Error in stream callback: {e}")
        
        def handle_approval():
            try:
                # Create a new event loop for the thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Set the stream callback for the chatbot
                chatbot_instance.stream_callback = stream_callback
                
                # Process tool approval response
                # Handle both single interrupt (backward compatibility) and multiple interrupts
                interrupt_ids = data.get('interrupt_ids', [data.get('interrupt_id', '')])
                approval_responses = data.get('approval_responses', [data.get('approval_response', 'deny')])
                
                # Ensure we have matching arrays
                if len(interrupt_ids) != len(approval_responses):
                    # If mismatch, use the first approval response for all interrupts
                    approval_responses = [approval_responses[0] if approval_responses else 'deny'] * len(interrupt_ids)
                
                result = loop.run_until_complete(
                    chatbot_instance.continue_with_tool_approval(
                        agent_name=data.get('agent_name', ''),
                        query=data.get('query', ''),
                        interrupt_ids=interrupt_ids,  # Changed to support multiple IDs
                        approval_responses=approval_responses,  # Changed to support multiple responses
                        pending_responses=data.get('pending_responses', []),
                        remaining_plan=data.get('remaining_plan', []),
                        original_query=data.get('original_query', '')
                    )
                )
                
                if result:
                    # Send the final result
                    socketio.emit(
                        "chat_response",
                        {
                            "type": "content",
                            "content": result,
                            "timestamp": datetime.now().isoformat(),
                        },
                        room=client_sid,
                    )
                
            except Exception as e:
                logger.error(f"Error processing tool approval response for connection {client_sid}: {e}")
                socketio.emit(
                    'chat_response',
                    {
                        'type': 'error',
                        'content': f"An error occurred while processing tool approval: {str(e)}",
                        'timestamp': datetime.now().isoformat()
                    },
                    room=client_sid
                )
            finally:
                loop.close()
        
        # Start processing in background thread
        process_thread = threading.Thread(target=handle_approval, daemon=True)
        process_thread.start()
        
        # Send immediate acknowledgment
        emit(
            "chat_response",
            {
                "type": "status",
                "content": f"Processing tool approval: {data.get('approval_response', 'unknown')}...",
                "timestamp": datetime.now().isoformat(),
            },
        )
        
    except Exception as e:
        logger.error(f"Error processing tool approval response for connection {client_sid}: {e}")
        emit('chat_response', {
            'type': 'error',
            'content': f"An error occurred while processing tool approval: {str(e)}",
            'timestamp': datetime.now().isoformat()
        })

@socketio.on("build_widget")
def handle_build_widget(data):
    """
    Handle widget building requests from the client.
    
    Args:
        data: Dictionary containing widget specifications
    """
    try:
        client_sid = request.sid
        
        # Get the chatbot instance for this connection
        chatbot_instance = get_chatbot_for_connection(client_sid)
        
        # Check if chatbot instance exists
        if not chatbot_instance:
            logger.error(f"Chatbot instance not found for connection {client_sid}")
            emit(
                "widget_response",
                {
                    "status": "error",
                    "message": "Dashboard system is not available. Please try reconnecting.",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return
            
        user_query = data.get("message", "").strip()
        
        # Define streaming callback for WebSocket
        async def stream_callback(update_data):
            """Callback function to stream responses."""
            try:
                socketio.emit(
                    "widget_update",
                    {**update_data, "timestamp": datetime.now().isoformat()},
                    room=client_sid,
                )
            except Exception as e:
                logger.error(f"Error in widget stream callback: {e}")
        
        def generate_widget():
            try:
                # Create a new event loop for the thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Generate the widget
                loop.run_until_complete(
                    chatbot_instance.process_message_stream(user_query, stream_callback, client_sid, client_sid, is_single_widget=True)
                )
                
                # Send success response
                socketio.emit(
                    "widget_response",
                    {
                        "status": "success",
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=client_sid,
                )
                
            except Exception as e:
                logger.error(f"Error generating widget for connection {client_sid}: {e}")
                socketio.emit(
                    "widget_response",
                    {
                        "status": "error",
                        "message": f"Failed to generate widget: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=client_sid,
                )
            finally:
                loop.close()
        
        # Start widget generation in background thread
        widget_thread = threading.Thread(target=generate_widget, daemon=True)
        widget_thread.start()
        
        # Send immediate acknowledgment
        emit(
            "widget_update",
            {
                "status": "processing",
                "message": "Generating widget...",
                "timestamp": datetime.now().isoformat(),
            },
        )
        
    except Exception as e:
        logger.error(f"Error handling widget build request for connection {client_sid}: {e}")
        emit("widget_response", {
            "status": "error",
            "message": f"An error occurred while building the widget: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })



if __name__ == "__main__":
    # Start the chatbot in a separate thread
    start_chatbot()
    
    print(f"Starting Flask-SocketIO server with logging level: {log_level}")
    print(f"Logs will be written to: {os.path.abspath('logs/backend.log')}")
    
    # Run the Flask-SocketIO server
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, allow_unsafe_werkzeug=True)
