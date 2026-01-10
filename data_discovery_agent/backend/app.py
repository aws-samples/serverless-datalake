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


# Global chatbot instance
chatbot = None
chatbot_lock = threading.Lock()


def start_chatbot():
    """Start the MCP chatbot in a separate thread."""
    global chatbot

    def run_chatbot():
        global chatbot
        sse_urls = []
        try:
            logger.info("Starting MCP chatbot initialization")
            
            # Load configuration
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'chatbot_config.json')
            if os.path.exists(config_path):
                logger.info(f"Loading configuration from {config_path}")
                config = ChatbotConfig.from_file(config_path)
            else:
                logger.info("Using default configuration")
                config = ChatbotConfig()
            
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
                    sse_urls = mcp_config.get('servers', [])
                logger.info(f"Loaded {len(sse_urls)} MCP servers from configuration file")
            except Exception as e:
                logger.error(f"Failed to load MCP servers from config file: {e}")
                logger.error("No MCP servers configured, chatbot will not be initialized")
                sys.exit(0)
                
                
            logger.info("Creating MCPClientChatbot instance with configuration")
            chatbot = MCPClientChatbot(sse_urls=sse_urls, config=config)
            # Start the chatbot (this will run in the background)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Start the chatbot with full initialization
            logger.info("Starting chatbot initialization")
            loop.run_until_complete(chatbot.start())
                
        except Exception as e:
            logger.error(f"Failed to start chatbot: {e}")
            logger.error(f"Error details: {str(e)}")
            logger.info("Running in demo mode without MCP servers")
            chatbot = None

    # Start chatbot in a separate thread
    thread = threading.Thread(target=run_chatbot, daemon=True)
    thread.start()
    
    # Give the thread a moment to initialize
    time.sleep(1)
    
    # Check if chatbot was initialized successfully
    with chatbot_lock:
        if chatbot is None:
            logger.error("Chatbot failed to initialize")
        else:
            logger.info("Chatbot thread started successfully")

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
        if chatbot and chatbot.config:
            return jsonify({
                "model": {
                    "primary_model_id": chatbot.config.model.primary_model_id,
                    "cheaper_model_id": chatbot.config.model.cheaper_model_id,
                    "max_tokens": chatbot.config.model.max_tokens,
                    "temperature": chatbot.config.model.temperature
                },
                "session": {
                    "session_timeout_minutes": chatbot.config.session.session_timeout_minutes,
                    "max_conversation_length": chatbot.config.session.max_conversation_length,
                    "enable_summarization": chatbot.config.session.enable_summarization,
                    "summarization_threshold": chatbot.config.session.summarization_threshold
                },
                "processing": {
                    "max_iterations": chatbot.config.processing.max_iterations,
                    "require_human_confirmation": chatbot.config.processing.require_human_confirmation,
                    "enable_parallel_execution": chatbot.config.processing.enable_parallel_execution,
                    "timeout_seconds": chatbot.config.processing.timeout_seconds
                },
                "dashboard": {
                    "output_directory": chatbot.config.dashboard.output_directory,
                    "enable_export": chatbot.config.dashboard.enable_export,
                    "default_chart_library": chatbot.config.dashboard.default_chart_library,
                    "max_datasets": chatbot.config.dashboard.max_datasets
                },
                "log_level": chatbot.config.log_level,
                "debug_mode": chatbot.config.debug_mode
            })
        else:
            return jsonify({"error": "Chatbot not initialized"}), 500
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"error": "Failed to get configuration"}), 500

@app.route("/api/config", methods=["POST"])
def update_config():
    """Update chatbot configuration."""
    try:
        if not chatbot:
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
        
        # Update the chatbot configuration
        chatbot.update_config(new_config)
        
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
        servers = {}
        for key, value in chatbot.mcp_clients.items():
            servers[key] = {
                "name": key,
                "status": "connected",
                "mcp_url": value["mcp_url"],
                "mcp_command": value["mcp_command"],
                "mcp_args": value["mcp_args"]
                
            }
        return jsonify({"timestamp": datetime.now().isoformat(), "servers": servers})

    except Exception as e:
        logger.error(f"MCP status check failed: {e}")
        return (
            jsonify({"error": "Failed to check MCP server status", "details": str(e)}),
            500,
        )


# socket event handlers
@socketio.on("connect")
def handle_connect():
    """Handle WebSocket connection."""
    try:
        client_id = request.sid
        logger.info(f"Client connecting: Socket ID {client_id}")
        
        # Check if chatbot exists
        if not chatbot:
            logger.error("Chatbot not initialized when handling connection")
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
                logger.info(f"Initializing conversation for session {client_id}")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Create agents for this session
                try:
                    chatbot.create_all_agents(user_id=client_id, session_id=client_id)
                    
                    # Verify that the orchestrator agent was created
                    if not chatbot.orchestrate_agent:
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
            finally:
                loop.close()

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
        chatbot.destroy_all_agents(session_id=client_id)
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
        # Check if chatbot exists
        if not chatbot:
            logger.error("Chatbot not initialized when handling chat message")
            emit(
                "chat_response",
                {
                    "type": "error",
                    "content": "Chat system is not available. Please try again later.",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return
            
        client_sid = request.sid
        # Check if orchestrator agent exists and create if needed
        if not chatbot.orchestrate_agent:
            logger.warning("Orchestrator agent not found, creating agents")
            try:
                chatbot.create_all_agents(user_id=client_sid, session_id=client_sid)
                if not chatbot.orchestrate_agent:
                    raise Exception("Failed to create orchestrator agent")
            except Exception as e:
                logger.error(f"Failed to create agents: {e}")
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
                    chatbot.process_message_stream(message, stream_callback, user_id=client_sid, session_id=client_sid)
                )
            except Exception as e:
                logger.error(f"Error processing message: {e}")
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
        logger.error(f"Error in chat_message handler: {e}")
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
                    chatbot.continue_with_confirmed_plan(
                        plan=data.get('plan', []),
                        original_query=data.get('original_query', ''),
                        is_single_widget=is_single_widget,
                        stream_callback=stream_callback,
                        user_id=client_sid,
                        session_id=client_sid
                    )
                )
            except Exception as e:
                logger.error(f"Error processing plan confirmation: {e}")
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
                chatbot.stream_callback = stream_callback
                
                # Process tool approval response
                result = loop.run_until_complete(
                    chatbot.continue_with_tool_approval(
                        agent_name=data.get('agent_name', ''),
                        query=data.get('query', ''),
                        interrupt_id=data.get('interrupt_id', ''),
                        approval_response=data.get('approval_response', 'deny'),
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
                logger.error(f"Error processing tool approval response: {e}")
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
        logger.error(f"Error processing tool approval response: {e}")
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
        # Check if chatbot exists
        if not chatbot:
            logger.error("Chatbot not initialized when handling widget build request")
            emit(
                "widget_response",
                {
                    "status": "error",
                    "message": "Dashboard system is not available. Please try again later.",
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
                    chatbot.process_message_stream(user_query, stream_callback, client_sid, client_sid, is_single_widget=True)
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
                logger.error(f"Error generating widget: {e}")
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
        logger.error(f"Error handling widget build request: {e}")
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
