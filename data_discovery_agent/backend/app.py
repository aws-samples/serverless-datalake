#!/usr/bin/env python3
"""
Flask API for Graph-based MCP Chatbot
Provides REST endpoints and SSE streaming for the React frontend to interact with MCP servers using graph execution.
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit, disconnect
import asyncio
import json
import logging
from datetime import datetime
import sys
import os
import pathlib
import signal
import atexit
import threading
import time

# Import from reorganized modules
from database.graph_integration import GraphIntegration, initialize_graph_system
from api.orchestrator_endpoints import orchestrator_bp
from config.chatbot_config import ChatbotConfig, ModelConfig, SessionConfig, ProcessingConfig, DashboardConfig

# Configure logging
import logging.config

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
            'level': 'ERROR',
            'propagate': False,
        },
        'engineio': {
            'handlers': ['default', 'file'],
            'level': 'ERROR',
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

# Register orchestrator endpoints
app.register_blueprint(orchestrator_bp)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)

# Global graph integration
graph_integration = None
config_global = None
active_sessions = {}
session_lock = threading.Lock()

def cleanup_all_sessions():
    """Clean up all active sessions."""
    global graph_integration, active_sessions
    
    logger.info("Starting cleanup of all sessions")
    
    # Clean up all active sessions
    with session_lock:
        active_sessions.clear()
    
    # Clean up the graph integration
    if graph_integration:
        try:
            logger.info("Cleaning up graph integration")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(graph_integration.cleanup())
            finally:
                loop.close()
            graph_integration = None
        except Exception as e:
            logger.error(f"Error cleaning up graph integration: {e}")
    
    logger.info("Session cleanup completed")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating shutdown")
    cleanup_all_sessions()
    sys.exit(0)

# Register signal handlers and cleanup
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup_all_sessions)

def start_graph_system():
    """Initialize the graph-based MCP system."""
    global graph_integration, config_global

    def run_initialization():
        global graph_integration, config_global
        try:
            logger.info("Starting graph-based MCP system initialization")
            
            # Load configuration
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'chatbot_config.json')
            if os.path.exists(config_path):
                logger.info(f"Loading configuration from {config_path}")
                config_global = ChatbotConfig.from_file(config_path)
            else:
                logger.info("Using default configuration")
                config_global = ChatbotConfig()
            
            # Initialize the graph system
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.info("Starting graph system initialization")
            try:
                success = loop.run_until_complete(initialize_graph_system())
                if success:
                    logger.info("Graph system initialized successfully")
                    # Get the global graph integration instance
                    from database.graph_integration import graph_integration as gi
                    graph_integration = gi
                else:
                    logger.error("Graph system initialization failed")
                    graph_integration = None
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Failed to start graph system: {e}")
            logger.error(f"Error details: {str(e)}")
            logger.info("Running in demo mode without MCP servers")
            graph_integration = None

    # Start graph system initialization in a separate thread
    thread = threading.Thread(target=run_initialization, daemon=True)
    thread.start()
    
    # Give the thread a moment to initialize vizro takes time
    time.sleep(15)
    
    # Check if graph system was initialized successfully
    if graph_integration is None:
        logger.error("Graph system failed to initialize")
    else:
        logger.info("Graph system started successfully")

# REST API Endpoints

@app.route("/api/health", methods=["GET"])
def api_health_check():
    """API health check endpoint."""
    try:
        # Check if graph system is available
        system_status = "healthy" if graph_integration else "unhealthy"
        
        return jsonify({
            "status": system_status,
            "timestamp": datetime.now().isoformat(),
            "service": "graph-mcp-chatbot-backend",
            "graph_system_available": graph_integration is not None
        }), 200
    except Exception as e:
        logger.error(f"API health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/api/mcp-status", methods=["GET"])
def get_mcp_status():
    """Get MCP server connection status."""
    try:
        if not graph_integration:
            return jsonify({
                "status": "error",
                "error": "Graph system not initialized",
                "servers": {},
                "timestamp": datetime.now().isoformat()
            }), 500
        
        # Get status from graph integration
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(graph_integration.get_connection_status())
        finally:
            loop.close()
        
        # Load MCP servers configuration for additional details
        mcp_config = {}
        try:
            import pathlib
            current_file = pathlib.Path(__file__)
            backend_dir = current_file.parent
            config_path = backend_dir / "mcp_servers.json"
            
            with open(config_path, 'r') as f:
                mcp_config_raw = json.load(f)
                mcp_config = mcp_config_raw.get("servers", {})
        except Exception as e:
            logger.warning(f"Could not load MCP config: {e}")
        
        # Format for frontend with additional server details
        servers = {}
        for name, connection_info in status.get("connections", {}).items():
            server_config = mcp_config.get(name, {})
            
            # Determine the status
            if connection_info.get("status") == "disabled":
                server_status = "disabled"
            elif connection_info.get("status") == "not_initialized":
                server_status = "not_initialized"
            elif connection_info.get("connected", False):
                server_status = "connected"
            else:
                server_status = "disconnected"
            
            servers[name] = {
                "name": server_config.get("name", name.title()),
                "status": server_status,
                "mcp_url": server_config.get("url", ""),
                "mcp_command": server_config.get("command", ""),
                "reconnection_attempts": connection_info.get("reconnection_attempts", 0),
                "max_attempts_reached": connection_info.get("max_attempts_reached", False),
                "disabled": server_config.get("disabled", False)
            }
        
        return jsonify({
            "status": "success",
            "servers": servers,
            "total_servers": status.get("total_clients", 0),
            "connected_servers": status.get("connected_clients", 0),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting MCP status: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "servers": {},
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/api/mcp-reconnect", methods=["POST"])
def reconnect_mcp():
    """Reconnect MCP servers."""
    try:
        data = request.get_json() or {}
        mcp_name = data.get("mcp_name")
        
        if not graph_integration:
            return jsonify({
                "status": "error",
                "error": "Graph system not initialized",
                "timestamp": datetime.now().isoformat()
            }), 500
        
        # Reinitialize MCP clients to detect newly started servers
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(graph_integration.reinitialize_mcp_clients())
        finally:
            loop.close()
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"MCP clients reinitialized successfully",
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "status": "error",
                "error": "Failed to reinitialize MCP clients",
                "timestamp": datetime.now().isoformat()
            }), 500
        
    except Exception as e:
        logger.error(f"Error reconnecting MCP: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500
    except Exception as e:
        logger.error(f"Error reconnecting MCP: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500
        # In a full implementation, you would call graph_integration.reconnect_mcp(mcp_name)
        
        return jsonify({
            "status": "success",
            "message": f"Reconnection attempted for {mcp_name if mcp_name else 'all MCP servers'}",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error reconnecting MCP servers: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

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
            return jsonify({"error": "Graph system not initialized"}), 500
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"error": "Failed to get configuration"}), 500

@app.route("/api/config", methods=["POST"])
def update_config():
    """Update chatbot configuration."""
    global config_global
    
    try:
        if not config_global:
            return jsonify({"error": "Graph system not initialized"}), 500
            
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
        
        # Update the graph integration
        if graph_integration:
            graph_integration.update_config(new_config)
        
        return jsonify({"message": "Configuration updated successfully"})
        
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"error": f"Failed to update configuration: {str(e)}"}), 500

# WebSocket Event Handlers

@socketio.on("connect")
def handle_connect():
    """Handle WebSocket connection."""
    try:
        client_id = request.sid
        logger.info(f"Client connecting: Socket ID {client_id}")
        
        # Check if graph system is available
        if not graph_integration:
            logger.error("Graph system not initialized when handling connection")
            emit(
                "connected",
                {
                    "status": "error",
                    "error": "Chat system is not available. Please try again later.",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return
        
        # Register the session
        with session_lock:
            active_sessions[client_id] = {
                "connected_at": datetime.now().isoformat(),
                "user_id": client_id,
                "session_id": client_id
            }
        
        # Emit connection success
        emit(
            "connected",
            {
                "status": "connected",
                "sid": client_id,
                "timestamp": datetime.now().isoformat(),
            },
        )
        
        logger.info(f"Client connected successfully: {client_id}")

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
    """Handle WebSocket disconnection."""
    try:
        client_id = request.sid
        
        emit("disconnected", {
            "status": "disconnected",
            "sid": client_id,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Remove from active sessions
        with session_lock:
            if client_id in active_sessions:
                del active_sessions[client_id]
                logger.info(f"Removed session for connection {client_id}")
        
    except Exception as e:
        logger.error(f"Error in WebSocket disconnect handler: {e}")

@socketio.on("ping")
def handle_ping():
    """Handle ping for connection testing."""
    emit("pong", {"timestamp": datetime.now().isoformat()})

@socketio.on("chat_message")
def handle_chat_message(data):
    """Handle chat messages through WebSocket with graph execution."""
    try:
        client_sid = request.sid
        
        # Check if graph system is available
        if not graph_integration:
            logger.error(f"Graph system not available for connection {client_sid}")
            emit(
                "chat_response",
                {
                    "type": "error",
                    "content": "Chat system is not available. Please try reconnecting.",
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

                # Process message with graph system
                from database.graph_integration import process_graph_query
                result = loop.run_until_complete(
                    process_graph_query(
                        message, 
                        client_sid, 
                        client_sid, 
                        stream_callback
                    )
                )
                
                # Send final result if needed
                if result.get("type") == "confirmation_needed":
                    socketio.emit(
                        "chat_response",
                        {
                            "type": "confirmation_needed",
                            "plan": result.get("plan", []),
                            "original_query": result.get("original_query", ""),
                            "timestamp": datetime.now().isoformat(),
                        },
                        room=client_sid,
                    )
                elif result.get("type") == "tool_approval_needed":
                    socketio.emit(
                        "chat_response",
                        {
                            "type": "tool_approval_needed",
                            **result.get("content", {}),
                            "timestamp": datetime.now().isoformat(),
                        },
                        room=client_sid,
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
    """Handle plan confirmation from client."""
    try:
        client_sid = request.sid
        
        if not graph_integration:
            logger.error(f"Graph system not available for connection {client_sid}")
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
                
                # Process plan confirmation
                from database.graph_integration import continue_graph_plan
                loop.run_until_complete(
                    continue_graph_plan(
                        plan=data.get('plan', []),
                        original_query=data.get('original_query', ''),
                        user_id=client_sid,
                        session_id=client_sid,
                        stream_callback=stream_callback
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

@socketio.on("reject_plan")
def handle_reject_plan(data):
    """Handle plan rejection from client."""
    try:
        client_sid = request.sid
        
        if not graph_integration:
            logger.error(f"Graph system not available for connection {client_sid}")
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
        
        def handle_rejection():
            try:
                # Create a new event loop for the thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Process plan rejection - restart with feedback
                original_query = data.get('original_query', '')
                rejection_reason = data.get('rejection_reason', 'User rejected the plan')
                
                # Create a contextual message that preserves the original query and adds feedback
                feedback_message = f"""The user has provided feedback on the previous plan:

ORIGINAL QUERY: {original_query}

USER FEEDBACK: {rejection_reason}

Please create a new plan that addresses this feedback while still answering the original query. Consider the user's specific suggestions and preferences."""
                
                from database.graph_integration import process_graph_query
                loop.run_until_complete(
                    process_graph_query(
                        query=feedback_message,
                        user_id=client_sid,
                        session_id=client_sid,
                        stream_callback=stream_callback
                    )
                )
            except Exception as e:
                logger.error(f"Error processing plan rejection for connection {client_sid}: {e}")
                socketio.emit(
                    'chat_response',
                    {
                        'type': 'error',
                        'content': f"An error occurred while processing the rejection: {str(e)}",
                        'timestamp': datetime.now().isoformat()
                    },
                    room=client_sid
                )
            finally:
                loop.close()
        
        # Start processing in background thread
        process_thread = threading.Thread(target=handle_rejection, daemon=True)
        process_thread.start()
        
        # Send immediate acknowledgment
        emit(
            "chat_response",
            {
                "type": "status",
                "content": "Processing plan rejection and creating new approach...",
                "timestamp": datetime.now().isoformat(),
            },
        )
        
    except Exception as e:
        logger.error(f"Error processing plan rejection: {e}")
        emit('chat_response', {
            'type': 'error',
            'content': f"An error occurred while processing the rejection: {str(e)}",
            'timestamp': datetime.now().isoformat()
        })

@socketio.on("tool_approval_response")
def handle_tool_approval_response(data):
    """Handle tool approval response from client."""
    try:
        client_sid = request.sid
        
        if not graph_integration:
            logger.error(f"Graph system not available for connection {client_sid}")
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
                
                # Process tool approval response
                from database.graph_integration import continue_graph_tool_approval
                
                # Handle both single interrupt (backward compatibility) and multiple interrupts
                interrupt_ids = data.get('interrupt_ids', [data.get('interrupt_id', '')])
                approval_responses = data.get('approval_responses', [data.get('approval_response', 'deny')])
                
                # Ensure we have matching arrays
                if len(interrupt_ids) != len(approval_responses):
                    approval_responses = [approval_responses[0] if approval_responses else 'deny'] * len(interrupt_ids)
                
                result = loop.run_until_complete(
                    continue_graph_tool_approval(
                        agent_name=data.get('agent_name', ''),
                        interrupt_ids=interrupt_ids,
                        approval_responses=approval_responses,
                        original_query=data.get('original_query', ''),
                        user_id=client_sid,
                        session_id=client_sid,
                        stream_callback=stream_callback
                    )
                )
                
                if result:
                    # Send the final result
                    socketio.emit(
                        "chat_response",
                        {
                            "type": "content",
                            "content": result.get("content", ""),
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

if __name__ == "__main__":
    # Start the graph system
    start_graph_system()
    
    print(f"Starting Graph-based MCP Chatbot server with logging level: {log_level}")
    print(f"Logs will be written to: {os.path.abspath('logs/backend.log')}")
    
    # Determine if we should run in debug mode
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    # Run the Flask-SocketIO server
    socketio.run(app, host="0.0.0.0", port=5001, debug=debug_mode, allow_unsafe_werkzeug=True)