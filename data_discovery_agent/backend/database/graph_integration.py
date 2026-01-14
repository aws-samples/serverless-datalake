"""
Integration module for the graph-based MCP chatbot system
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import pathlib
import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .graph_mcp_chatbot import GraphMCPChatbot
from config.chatbot_config import ChatbotConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)

class GraphIntegration:
    """Integration class for managing the graph-based MCP chatbot."""
    
    def __init__(self):
        self.chatbot = None
        self.config = DEFAULT_CONFIG
        self._is_initialized = False
        
    async def initialize(self, config_path: str = None):
        """Initialize the graph chatbot with MCP servers configuration."""
        try:
            if self._is_initialized:
                logger.info("Graph integration already initialized")
                return True
                
            # Load MCP servers configuration
            if not config_path:
                current_file = pathlib.Path(__file__)
                backend_dir = current_file.parent.parent
                config_path = backend_dir / "mcp_servers.json"
            
            with open(config_path, 'r') as f:
                mcp_config_raw = json.load(f)
            
            # Extract servers from the configuration
            if "servers" in mcp_config_raw:
                mcp_config = mcp_config_raw["servers"]
            else:
                mcp_config = mcp_config_raw
            
            logger.info(f"Loaded MCP configuration with {len(mcp_config)} servers")
            
            # Create and start the chatbot
            self.chatbot = GraphMCPChatbot(
                sse_urls=mcp_config,
                config=self.config
            )
            
            success = await self.chatbot.start()
            if success:
                self._is_initialized = True
                logger.info("Graph integration initialized successfully")
                return True
            else:
                logger.error("Failed to start graph chatbot")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing graph integration: {e}")
            return False
    
    async def process_query(
        self, 
        query: str, 
        user_id: str = "default", 
        session_id: str = "default",
        stream_callback=None
    ) -> Dict[str, Any]:
        """Process a query using the graph-based chatbot."""
        try:
            if not self._is_initialized:
                await self.initialize()
            
            if not self.chatbot:
                raise Exception("Chatbot not initialized")
            
            logger.info(f"Processing query for user {user_id}, session {session_id}")
            
            # Process the message with streaming
            result = await self.chatbot.process_message_stream(
                message=query,
                stream_callback=stream_callback,
                user_id=user_id,
                session_id=session_id
            )
            
            return {
                "status": "success" if result.get("type") != "error" else "error",
                "response": result.get("content", ""),
                "type": result.get("type", "unknown"),
                "metadata": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "status": "error",
                "response": f"An error occurred while processing your query: {str(e)}",
                "type": "error",
                "error": str(e),
                "metadata": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    async def continue_with_plan(
        self,
        plan: list,
        original_query: str,
        user_id: str = "default",
        session_id: str = "default",
        stream_callback=None
    ) -> Dict[str, Any]:
        """Continue processing with a confirmed plan."""
        try:
            if not self._is_initialized:
                await self.initialize()
            
            if not self.chatbot:
                raise Exception("Chatbot not initialized")
            
            logger.info(f"Continuing with confirmed plan for user {user_id}, session {session_id}")
            
            result = await self.chatbot.continue_with_confirmed_plan(
                plan=plan,
                original_query=original_query,
                stream_callback=stream_callback,
                user_id=user_id,
                session_id=session_id
            )
            
            return {
                "status": "success" if result.get("type") != "error" else "error",
                "response": result.get("content", ""),
                "type": result.get("type", "unknown"),
                "metadata": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "original_query": original_query,
                    "plan": plan,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error continuing with plan: {e}")
            return {
                "status": "error",
                "response": f"An error occurred while executing the plan: {str(e)}",
                "type": "error",
                "error": str(e),
                "metadata": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "original_query": original_query,
                    "plan": plan,
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get information about the graph system."""
        try:
            if not self._is_initialized or not self.chatbot:
                return {
                    "status": "not_initialized",
                    "initialized": False,
                    "available_agents": [],
                    "config": self.config.__dict__ if hasattr(self.config, '__dict__') else str(self.config)
                }
            
            # Get available tools/agents
            available_tools = self.chatbot.get_all_available_tools()
            
            return {
                "status": "initialized",
                "initialized": True,
                "system_type": "graph_based",
                "available_agents": available_tools,
                "agent_count": len(available_tools),
                "config": {
                    "max_iterations": self.config.processing.max_iterations,
                    "require_human_confirmation": self.config.processing.require_human_confirmation,
                    "primary_model": self.config.model.primary_model_id,
                    "cheaper_model": self.config.model.cheaper_model_id,
                    "log_level": self.config.log_level
                },
                "mcp_clients": len(self.chatbot.mcp_clients) if self.chatbot else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {
                "status": "error",
                "initialized": False,
                "error": str(e),
                "available_agents": []
            }
    
    async def reinitialize_mcp_clients(self) -> bool:
        """Reinitialize MCP clients to detect newly started servers."""
        try:
            if not self._is_initialized or not self.chatbot:
                logger.error("Graph system not initialized")
                return False
            
            return await self.chatbot.reinitialize_mcp_clients()
            
        except Exception as e:
            logger.error(f"Error reinitializing MCP clients: {e}")
            return False

    async def get_connection_status(self) -> Dict[str, Any]:
        """Get the connection status of all MCP clients."""
        try:
            if not self._is_initialized or not self.chatbot:
                return {
                    "status": "not_initialized",
                    "connections": {}
                }
            
            # Get all configured servers from the chatbot's sse_urls (mcp_servers.json)
            connections = {}
            
            # First, add all configured servers (even if not initialized)
            for mcp_name, server_config in self.chatbot.sse_urls.items():
                if server_config.get("disabled", False):
                    connections[mcp_name] = {
                        "connected": False,
                        "status": "disabled",
                        "reconnection_attempts": 0,
                        "max_attempts_reached": False
                    }
                elif mcp_name.lower() in self.chatbot.mcp_clients:
                    # Server is initialized, test actual connection
                    try:
                        is_connected = await self.chatbot._test_mcp_connection(mcp_name.lower())
                        connections[mcp_name] = {
                            "connected": is_connected,
                            "status": "connected" if is_connected else "disconnected",
                            "reconnection_attempts": self.chatbot._reconnection_attempts.get(mcp_name.lower(), 0),
                            "max_attempts_reached": self.chatbot._reconnection_attempts.get(mcp_name.lower(), 0) >= self.chatbot._max_reconnection_attempts
                        }
                    except Exception as e:
                        logger.error(f"Error testing connection for {mcp_name}: {e}")
                        connections[mcp_name] = {
                            "connected": False,
                            "status": "disconnected",
                            "reconnection_attempts": self.chatbot._reconnection_attempts.get(mcp_name.lower(), 0),
                            "max_attempts_reached": True,
                            "error": str(e)
                        }
                else:
                    # Server is configured but not initialized
                    connections[mcp_name] = {
                        "connected": False,
                        "status": "not_initialized",
                        "reconnection_attempts": self.chatbot._reconnection_attempts.get(mcp_name.lower(), 0),
                        "max_attempts_reached": False
                    }
            
            return {
                "status": "success",
                "connections": connections,
                "total_clients": len(connections),
                "connected_clients": len([c for c in connections.values() if c.get("connected", False)])
            }
            
        except Exception as e:
            logger.error(f"Error getting connection status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "connections": {}
            }
    
    def update_config(self, new_config: ChatbotConfig):
        """Update the chatbot configuration."""
        try:
            self.config = new_config
            if self.chatbot:
                self.chatbot.update_config(new_config)
            logger.info("Configuration updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.chatbot:
                await self.chatbot.cleanup()
            self._is_initialized = False
            logger.info("Graph integration cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# Global instance
graph_integration = GraphIntegration()

# Convenience functions for API endpoints
async def process_graph_query(
    query: str, 
    user_id: str = "default", 
    session_id: str = "default",
    stream_callback=None
) -> Dict[str, Any]:
    """Process a query using the graph-based system."""
    return await graph_integration.process_query(query, user_id, session_id, stream_callback)

async def continue_graph_plan(
    plan: list,
    original_query: str,
    user_id: str = "default",
    session_id: str = "default",
    stream_callback=None
) -> Dict[str, Any]:
    """Continue with a confirmed plan."""
    return await graph_integration.continue_with_plan(
        plan, original_query, user_id, session_id, stream_callback
    )

def get_graph_info() -> Dict[str, Any]:
    """Get information about the graph system."""
    return graph_integration.get_system_info()

async def get_graph_status() -> Dict[str, Any]:
    """Get the status of the graph system."""
    return await graph_integration.get_connection_status()

async def continue_graph_tool_approval(
    agent_name: str,
    interrupt_ids: list,
    approval_responses: list,
    original_query: str = None,
    user_id: str = "default",
    session_id: str = "default",
    stream_callback=None
) -> Dict[str, Any]:
    """Continue with tool approval."""
    if not graph_integration.chatbot:
        await graph_integration.initialize()
    
    # Set up streaming callback
    if stream_callback:
        graph_integration.chatbot.stream_callback = stream_callback
    
    return await graph_integration.chatbot.continue_with_tool_approval(
        agent_name, interrupt_ids, approval_responses, original_query
    )

# Initialize on import
async def initialize_graph_system():
    """Initialize the graph system."""
    return await graph_integration.initialize()
