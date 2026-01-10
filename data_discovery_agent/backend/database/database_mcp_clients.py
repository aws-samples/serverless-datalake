from mcp import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.client.sse import sse_client
from strands import Agent
from strands.tools.mcp import MCPClient
from strands.models import BedrockModel
import asyncio
import json
import logging
from datetime import datetime
import re
from typing import Optional, Dict, Any, List, Tuple
import os
import base64
import uuid
from textwrap import dedent
from strands.agent.conversation_manager import SummarizingConversationManager,NullConversationManager,SlidingWindowConversationManager
from strands.session.file_session_manager import FileSessionManager
import time
import pathlib
from dataclasses import dataclass
from enum import Enum
import sys
import os
# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.chatbot_config import ChatbotConfig, DEFAULT_CONFIG
from .hooks import MCPToolApprovalHook
from .hooks.approval_hooks import (
    set_always_approve_for_tool, 
    remove_always_approve_for_tool, 
    is_tool_always_approved,
    get_always_approved_tools
)
from utils.response_summarizer import ResponseSummarizer, quick_summarize
from utils.prompts import PromptTemplates
from utils.models import ResponseType, AgentResponse, JsonFormatter
from utils.json_utils import extract_and_fix_json, extract_and_merge_json, get_json_key
from utils.conversation_history_rebuilder import ConversationHistoryRebuilder
# Configure logging
import sys

def setup_logging(config: ChatbotConfig):
    """Setup logging based on configuration."""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    # Create logs directory in project root if it doesn't exist
    current_file = pathlib.Path(__file__)
    project_root = current_file.parent.parent.parent
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True, parents=True)
    
    log_file_path = logs_dir / "database_mcp_clients.log"
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_file_path))
        ]
    )
    
    # Set specific logger level
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    return logger

# Initialize with default config for now - will be updated when chatbot is created
logger = setup_logging(DEFAULT_CONFIG)

logger.setLevel(logging.INFO)

class MCPClientChatbot:
    """
    A persistent chatbot that connects to any database MCP server and stays running
    for continuous database interactions.
    
    This class provides unified MCP client management with:
    - Automatic health checks and reconnection
    - Configuration preservation across reconnections
    - Consistent client creation and management
    - Support for multiple transport types (SSE, stdio, streamable_http)
    """

    def __init__(
        self,
        sse_urls: list[dict] = [],
        stream_callback=None,
        config: ChatbotConfig = None,
    ):
        """
        Initialize the MCP Chatbot.

        Args:
            sse_urls (list[{"name": str, "url": str}]): List of MCP servers with their names and URLs
            stream_callback: Optional callback function for streaming data
            config: ChatbotConfig instance, defaults to DEFAULT_CONFIG
        """
        self.sse_urls = sse_urls
        self.is_running = False
        self.stream_callback = stream_callback
        self.mcp_clients = {}
        self._health_check_task = None
        self._health_check_interval = 30  # seconds
        self._reconnection_attempts = {}
        self._max_reconnection_attempts = 3
        # Initialize conversation history rebuilder
        self.rebuilder = ConversationHistoryRebuilder()
        
        # Use provided config or default
        self.config = config or DEFAULT_CONFIG
        
        # Initialize models using config
        self.model = BedrockModel(
            model_id=self.config.model.primary_model_id
        )
        self.cheaper_model = BedrockModel(
            model_id=self.config.model.cheaper_model_id
        )
        
        self.agent = None
        self.orchestrator_agent = None
        self.verifier_agent = None

        self.conversation_manager = None
        self.multi_session_manager = None
        self.collected_datasets = []
        self.total_datasets=0
        self.response_summarizer = None
        
    async def _handle_error(self, error_message: str, context: str = ""):
        """Handle errors consistently with proper logging and user feedback."""
        full_message = f"{context}: {error_message}" if context else error_message
        logger.error(full_message)
        await self._stream_update("error", error_message)
        await self._stream_update("end", timestamp=datetime.now().isoformat())
            
    def verifier_agent_builder(self):
        """Verifier agent to check if the query is resolved."""
        try:
            logger.info("Building verifier agent")
            verifier_prompt = PromptTemplates.get_verifier_agent_prompt()
            self.verifier_agent = Agent(
                system_prompt=verifier_prompt, 
                model=self.model, 
                name="Verifier_Agent",
                conversation_manager=self.conversation_manager, 
                session_manager=self.multi_session_manager,
                agent_id=str(uuid.uuid4())
            )
            logger.info("Verifier agent created successfully")
        except Exception as e:
            logger.error(f"Error creating verifier agent: {e}")
            # Set to None to ensure we know it failed
            self.verifier_agent = None
            raise e

    def orchestrate_agent_builder(self):
        """Orchestrate the agent to process the message."""
        orchestrator_prompt = PromptTemplates.get_orchestrator_agent_prompt(
            list(self.mcp_clients.values())
        )
        try:
            logger.info("Building orchestrator agent")
            self.orchestrate_agent = Agent(
                system_prompt=orchestrator_prompt, 
                model=self.model,
                conversation_manager=self.conversation_manager, 
                session_manager=self.multi_session_manager,
                agent_id=str(uuid.uuid4())
            )
            logger.info("Orchestrator agent created successfully")
        except Exception as e:
            logger.error(f"Error creating orchestrator agent: {e}")
            # Set to None to ensure we know it failed
            self.orchestrate_agent = None
            raise e

    def refresh_orchestrator_agent(self):
        """Refresh the orchestrator agent with updated MCP client list."""
        try:
            logger.info("Refreshing orchestrator agent with updated MCP clients")
            
            # Get the current list of available agents
            available_agents = list(self.mcp_clients.values())
            logger.info(f"Available agents for orchestrator: {[agent.get('name', 'Unknown') for agent in available_agents]}")
            
            # Rebuild the orchestrator prompt with updated agent list
            orchestrator_prompt = PromptTemplates.get_orchestrator_agent_prompt(available_agents)
            
            # Update the existing orchestrator agent's system prompt if it exists
            if self.orchestrate_agent:
                # Create a new orchestrator agent with updated prompt
                self.orchestrate_agent = Agent(
                    system_prompt=orchestrator_prompt, 
                    model=self.model,
                    conversation_manager=self.conversation_manager, 
                    session_manager=self.multi_session_manager,
                    agent_id=str(uuid.uuid4())
                )
                logger.info("Orchestrator agent refreshed successfully")
            else:
                # If orchestrator doesn't exist, create it
                self.orchestrate_agent_builder()
                logger.info("Orchestrator agent created during refresh")
                
        except Exception as e:
            logger.error(f"Error refreshing orchestrator agent: {e}")
            # Don't raise the exception to avoid breaking the reconnection process
            logger.warning("Continuing without orchestrator agent refresh")

    def _create_mcp_client(self, mcp_config: dict) -> MCPClient:
        """
        Create an MCP client based on the configuration.
        
        Args:
            mcp_config: Configuration dictionary containing connection details
            
        Returns:
            MCPClient instance
        """
        if mcp_config["is_sse"]:
            headers = mcp_config.get("headers", {})
            return MCPClient(lambda: sse_client(mcp_config["mcp_url"], headers=headers))
        elif mcp_config["is_stdio"]:
            return MCPClient(lambda: stdio_client(
                StdioServerParameters(
                    command=mcp_config["mcp_command"], 
                    args=mcp_config["mcp_args"]
                )
            ))
        elif mcp_config["is_streamable_http"]:
            return MCPClient(lambda: streamable_http_client(mcp_config["mcp_url"]))
        else:
            raise ValueError(f"Unknown transport type for MCP client")

    async def _initialize_mcp_client(self, mcp_name: str, server_config: dict) -> bool:
        """
        Initialize or reinitialize a single MCP client.
        
        Args:
            mcp_name: Name of the MCP server
            server_config: Raw server configuration from JSON
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Initializing {mcp_name} MCP client")
            
            # Process server configuration to internal format
            processed_config = self._process_server_config(mcp_name, server_config)
            
            # Create MCP client
            mcp_client = self._create_mcp_client(processed_config)
            
            # Test connection and get tools
            with mcp_client:
                tools = mcp_client.list_tools_sync()
                
                # Build tool configuration
                tool_config = []
                for tool in tools:
                    tool_config.append({
                        "name": tool.tool_name,
                        "description": tool.tool_spec["description"],
                        "inputSchema": tool.tool_spec["inputSchema"],
                    })
                
                # Store the complete configuration
                self.mcp_clients[mcp_name.lower()] = self._preserve_server_config(
                    mcp_name, server_config, tool_config, is_reconnection=False
                )
                
                logger.info(f"Successfully initialized {mcp_name} MCP client with {len(tools)} tools")
                return True
                
        except Exception as e:
            logger.error(f"Error initializing {mcp_name} MCP client: {e}")
            return False

    def _process_server_config(self, mcp_name: str, server_config: dict) -> dict:
        """
        Process raw server configuration into internal format.
        
        Args:
            mcp_name: Name of the MCP server
            server_config: Raw server configuration from JSON
            
        Returns:
            Processed configuration dictionary
        """
        # Determine transport type
        transport_type = server_config.get("transportType", "stdio")
        
        return {
            "name": server_config.get("name", mcp_name),
            "is_streamable_http": transport_type == "streamable_http",
            "is_sse": transport_type == "sse", 
            "is_stdio": transport_type not in ["streamable_http", "sse"],
            "mcp_url": server_config.get("url", ""),
            "mcp_command": server_config.get("command", ""),
            "mcp_args": server_config.get("args", ""),
            "headers": server_config.get("headers", {}),
        }

    def _preserve_server_config(self, mcp_name: str, server_config: dict, tool_config: list, is_reconnection: bool = False) -> dict:
        """
        Preserve all server configuration parameters when updating MCP client config.
        
        Args:
            mcp_name: Name of the MCP server
            server_config: Original server configuration (or existing mcp_client config for reconnection)
            tool_config: Updated tool configuration
            is_reconnection: True if this is a reconnection (config already processed), False for initial setup
            
        Returns:
            Complete configuration dictionary with all parameters preserved
        """
        if is_reconnection:
            # For reconnection, server_config is already the processed mcp_client config
            # Just update the tools and preserve everything else
            logger.debug(f"Preserving all configuration parameters for {mcp_name} during reconnection")
            return {**server_config, "tools": tool_config}
        else:
            # For initial setup, process the raw server config from JSON
            # Standard configuration keys that we handle explicitly
            standard_keys = {
                "name", "agent_type", "usage", "url", "command", "args", 
                "transportType", "rules_prompt", "description", "headers", 
                "disabled", "output_location"
            }
            
            # Extract standard parameters
            base_config = {
                "agent_type": server_config.get("agent_type", "Others"),
                "name": server_config.get("name", mcp_name),
                "description": server_config.get("description", ""),
                "is_streamable_http": server_config.get("transportType") == "streamable_http",
                "is_sse": server_config.get("transportType") == "sse",
                "is_stdio": server_config.get("transportType") not in ["streamable_http", "sse"],
                "mcp_url": server_config.get("url", ""),
                "mcp_command": server_config.get("command", ""),
                "mcp_args": server_config.get("args", ""),
                "tools": tool_config,
                "rules_prompt": server_config.get("rules_prompt", ""),
                "usage": server_config.get("usage", ""),
                "headers": server_config.get("headers", {}),
                "output_location": server_config.get("output_location", ""),
                "transportType": server_config.get("transportType", ""),
            }
            
            # Preserve any custom parameters not in the standard set
            custom_params = {k: v for k, v in server_config.items() if k not in standard_keys}
            
            if custom_params:
                logger.debug(f"Preserving custom configuration parameters for {mcp_name}: {list(custom_params.keys())}")
            
            # Combine base config with custom parameters
            return {**base_config, **custom_params}
        """
        Preserve all server configuration parameters when updating MCP client config.
        
        Args:
            mcp_name: Name of the MCP server
            server_config: Original server configuration (or existing mcp_client config for reconnection)
            tool_config: Updated tool configuration
            is_reconnection: True if this is a reconnection (config already processed), False for initial setup
            
        Returns:
            Complete configuration dictionary with all parameters preserved
        """
        if is_reconnection:
            # For reconnection, server_config is already the processed mcp_client config
            # Just update the tools and preserve everything else
            logger.debug(f"Preserving all configuration parameters for {mcp_name} during reconnection")
            return {**server_config, "tools": tool_config}
        else:
            # For initial setup, process the raw server config from JSON
            # Standard configuration keys that we handle explicitly
            standard_keys = {
                "name", "agent_type", "usage", "url", "command", "args", 
                "transportType", "rules_prompt", "description", "headers", 
                "disabled", "output_location"
            }
            
            # Extract standard parameters
            base_config = {
                "agent_type": server_config.get("agent_type", "Others"),
                "name": server_config.get("name", mcp_name),
                "description": server_config.get("description", ""),
                "is_streamable_http": server_config.get("transportType") == "streamable_http",
                "is_sse": server_config.get("transportType") == "sse",
                "is_stdio": server_config.get("transportType") not in ["streamable_http", "sse"],
                "mcp_url": server_config.get("url", ""),
                "mcp_command": server_config.get("command", ""),
                "mcp_args": server_config.get("args", ""),
                "tools": tool_config,
                "rules_prompt": server_config.get("rules_prompt", ""),
                "usage": server_config.get("usage", ""),
                "headers": server_config.get("headers", {}),
                "output_location": server_config.get("output_location", ""),
                "transportType": server_config.get("transportType", ""),
            }
            
            # Preserve any custom parameters not in the standard set
            custom_params = {k: v for k, v in server_config.items() if k not in standard_keys}
            
            if custom_params:
                logger.debug(f"Preserving custom configuration parameters for {mcp_name}: {list(custom_params.keys())}")
            
            # Combine base config with custom parameters
            return {**base_config, **custom_params}

    async def start(self):
        """Start the chatbot and initialize all components."""
        try:
            self.is_running = True
            print("🤖 Starting MCP Chatbot...")
            print("=" * 50)
            logger.info("Starting MCP Chatbot")
            
            # Initialize MCP clients
            for mcp_name, server_config in self.sse_urls.items():
                # Skip disabled servers
                if server_config.get("disabled", False):
                    logger.info(f"Skipping disabled MCP server: {mcp_name}")
                    continue
                    
                # Use the unified initialization method
                success = await self._initialize_mcp_client(mcp_name, server_config)
                if success:
                    print(f"🛠️ Initialized {mcp_name} MCP client")
                else:
                    print(f"❌ Failed to initialize {mcp_name} MCP client")
            
            print("✅ MCP Chatbot started successfully")
            print("🎯 Chatbot is ready to process requests via API!")
            # print("📊 Dashboard building capabilities enabled!")
            print("=" * 50)
            
            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            logger.info("MCP Chatbot started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting chatbot: {e}")
            print(f"❌ Failed to start chatbot: {e}")
            self.is_running = False
            raise e

    async def force_reconnect_all(self):
        """Force reconnection of all MCP clients."""
        logger.info("Force reconnecting all MCP clients")
        
        for mcp_name, mcp_config in self.mcp_clients.items():
            # Reset reconnection attempts
            self._reconnection_attempts[mcp_name] = 0
            await self._reconnect_mcp_client(mcp_name, mcp_config)
        
        # Refresh orchestrator agent with updated MCP clients
        self.refresh_orchestrator_agent()

    async def force_reconnect_client(self, mcp_name: str):
        """Force reconnection of a specific MCP client."""
        if mcp_name not in self.mcp_clients:
            logger.error(f"MCP client {mcp_name} not found")
            return False
            
        logger.info(f"Force reconnecting MCP client: {mcp_name}")
        
        # Reset reconnection attempts
        self._reconnection_attempts[mcp_name] = 0
        result = await self._reconnect_mcp_client(mcp_name, self.mcp_clients[mcp_name.lower()])
        
        # Refresh orchestrator agent with updated MCP clients
        if result:
            self.refresh_orchestrator_agent()
            
        return result

    async def refresh_mcp_client(self, mcp_name: str, server_config: dict):
        """Refresh an MCP client with new configuration."""
        logger.info(f"Refreshing MCP client: {mcp_name}")
        
        # Reset reconnection attempts
        self._reconnection_attempts[mcp_name] = 0
        
        # Use the unified initialization method
        result = await self._initialize_mcp_client(mcp_name, server_config)
        
        # Refresh orchestrator agent with updated MCP clients
        if result:
            self.refresh_orchestrator_agent()
            
        return result
    
    def conversation_manager_builder(self):
        """Build the conversation manager with summarization capabilities."""
        try:
            # Create response summarizer utility
            self.response_summarizer = ResponseSummarizer(model_id=self.config.model.cheaper_model_id)
            logger.info("Building conversation manager")
            # Use configuration to determine conversation manager type
            if self.config.session.enable_summarization:
                self.conversation_manager = SummarizingConversationManager(
                    summary_ratio=0.5,  # Could be made configurable
                    preserve_recent_messages=self.config.session.summarization_threshold // 5,
                    summarization_agent=self.response_summarizer.agent
                )
                logger.info("Created summarizing conversation manager")
            else:
                self.conversation_manager = NullConversationManager()
                logger.info("Created null conversation manager")
            
            
            logger.info("Created response summarizer utility")
                
        except Exception as e:
            logger.error(f"Error creating conversation manager: {e}")
            # Set to None to ensure we know it failed
            self.conversation_manager = None
            raise e

    def agent_builder(self, mcp_name, specialized_agent_mcp_rules_prompt, tools, tool_config):
        
        AGENT_SYSTEM_PROMPT = PromptTemplates.get_specialized_agent_prompt().format(
            placeholder=str(tool_config), 
            agent_special_rules=f"2. Rules: {specialized_agent_mcp_rules_prompt}"
        )
        
        # Create approval hook for this agent
        approval_hook = MCPToolApprovalHook(
            app_name=f"{mcp_name}_agent",
            tools_requiring_approval=None,  # Will use default list
            auto_approve_patterns=None      # Will use default patterns
        )

        previous_messages=[]
        # Restore conversation history for this specialized agent
        try:
            if self.multi_session_manager and hasattr(self.multi_session_manager, 'session_id'):
                session_id = self.multi_session_manager.session_id
                logger.info(f"Attempting to restore conversation history for specialized agent '{mcp_name}' in session '{session_id}'")
                # Get conversations for all specialized agents in this session
                specialized_conversations = self.rebuilder.get_specialized_agent_conversations(session_id)
                
                # Check if we have previous conversation for this specialized agent
                if mcp_name in specialized_conversations:
                    previous_messages = specialized_conversations[mcp_name]
                    logger.info(f"Found {len(previous_messages)} previous messages for specialized agent '{mcp_name}'")
                else:
                    logger.info(f"No previous conversation found for specialized agent '{mcp_name}' - starting fresh")
            else:
                logger.warning("Session manager not available or missing session_id - cannot restore conversation history")
                
        except Exception as e:
            logger.error(f"Error restoring conversation history for specialized agent '{mcp_name}': {e}")
            # Don't fail agent creation if conversation restoration fails
            logger.info(f"Continuing with fresh conversation for specialized agent '{mcp_name}'")
        
        
        # Specialized MCP agent
        agent = Agent(
                name=mcp_name,
                tools=tools,
                model=self.model,
                system_prompt=AGENT_SYSTEM_PROMPT,
                conversation_manager=self.conversation_manager, 
                messages=previous_messages,
                session_manager=self.multi_session_manager,
                hooks=[approval_hook],  # Add the approval hook
                agent_id=str(uuid.uuid4())
            )
        agent.state.set("specialized_agent", mcp_name)
        
        
        return agent
    
    async def callback_handler(self, chunk):
        """Handle the callback from the agent."""
        full_response = ""
        if "data" in chunk:
            await self._stream_update("thinking", chunk["data"])
            full_response += chunk["data"]
        elif "complete" in chunk:
            await self._stream_update("thinking", chunk["complete"], is_partial=False)
            full_response += chunk["complete"]
        elif "current_tool_use" in chunk:
            await self._stream_update(
                "tool_use",
                chunk["current_tool_use"].get("name"),
                extra={"input": chunk["current_tool_use"].get("input", "")},
            )
        elif "reasoningText" in chunk:
            await self._stream_update("thinking", chunk["reasoningText"])
        return full_response

    def get_mcp_client(self, mcp_name):
        """Get the MCP client."""
        if mcp_name not in self.mcp_clients:
            return None
            
        mcp_config = self.mcp_clients[mcp_name.lower()]
        return self._create_mcp_client(mcp_config)
    
    def create_all_agents(self, user_id, session_id=None):
        """Create all agents needed for the chatbot."""
        try:
            logger.info(f"Creating all agents for user {user_id}, session {session_id}")
            
            # Create session manager with project-relative path
            current_file = pathlib.Path(__file__)
            project_root = current_file.parent.parent.parent
            sessions_dir = project_root / "user_sessions"
            sessions_dir.mkdir(exist_ok=True, parents=True)
            
            self.multi_session_manager = FileSessionManager(session_id=f"{user_id}_{session_id}", storage_dir=str(sessions_dir))
            logger.info(f"Multi-Session manager created with ID: {user_id}_{session_id}")
            
            # Create conversation manager
            self.conversation_manager_builder()
            logger.info("Conversation manager created")
            
            # Create orchestrator agent
            self.orchestrate_agent_builder()
            logger.info("Orchestrator agent created")
            
            # Create verifier agent
            self.verifier_agent_builder()
            logger.info("Verifier agent created")
            
            # Reset dataset collection (configurable max datasets)
            self.collected_datasets = []
            self.total_datasets = 0
            
            logger.info("All agents created successfully")
        except Exception as e:
            logger.error(f"Error creating agents: {e}")
            raise e
    
    def destroy_all_agents(self, user_id="Sample", session_id=None):
        """Clean up all agents and resources."""
        self.conversation_manager = None
        self.orchestrate_agent = None
        self.verifier_agent = None
        
        # Clean up response summarizer
        if self.response_summarizer:
            self.response_summarizer = None
        
        # Clear collected data
        self.collected_datasets = []
        self.total_datasets = 0
        
        logger.info(f"All agents destroyed for user {user_id}, session {session_id}")

    def update_config(self, new_config: ChatbotConfig):
        """Update the chatbot configuration and reinitialize components as needed."""
        self.config = new_config
        
        # Update models with new configuration
        self.model = BedrockModel(model_id=self.config.model.primary_model_id)
        self.cheaper_model = BedrockModel(model_id=self.config.model.cheaper_model_id)
        
        # Update response summarizer if it exists
        if self.response_summarizer:
            self.response_summarizer = ResponseSummarizer(
                model_id=self.config.model.cheaper_model_id)
        
        # Update logger
        global logger
        logger = setup_logging(self.config)
        
        logger.info(f"Configuration updated: {self.config}")

    def set_tool_always_approve(self, tool_name: str):
        """Set a specific tool to always be approved without asking."""
        set_always_approve_for_tool(tool_name)
        logger.info(f"Tool {tool_name} set to always approve")

    def remove_tool_always_approve(self, tool_name: str):
        """Remove a tool from the always approve list."""
        remove_always_approve_for_tool(tool_name)
        logger.info(f"Tool {tool_name} removed from always approve list")

    def is_tool_always_approved(self, tool_name: str) -> bool:
        """Check if a tool is set to always approve."""
        return is_tool_always_approved(tool_name)

    def get_always_approved_tools(self) -> List[str]:
        """Get list of all tools that are always approved."""
        return get_always_approved_tools()

    def clear_all_always_approvals(self):
        """Clear all always approve settings."""
        from .hooks.approval_hooks import _always_approve_cache
        _always_approve_cache.clear()
        logger.info("Cleared all always approve settings")

    async def _stream_update(
        self,
        update_type: str,
        content: str = "",
        is_partial: bool = True,
        timestamp: str = None,
        metadata: dict = None,
        extra: dict = None,
        title: str = None,
    ):
        """Send streaming updates via callback."""
        if self.stream_callback:
            clean_content = content
            update_data = {
                "type": update_type,
                "content": clean_content,
                "is_partial": is_partial,
            }
            if update_type == "tool_use":
                del update_data["content"]
                update_data["tool"] = clean_content
                update_data["input"] = extra["input"] if "input" in extra else {}
            if timestamp:
                update_data["timestamp"] = timestamp
            if metadata:
                update_data["metadata"] = metadata
            if title:
                update_data["title"] = title
            if extra:
                update_data.update(extra)
            await self.stream_callback(update_data)
            
    async def _handle_error(self, error_message):
        """Handle errors consistently with proper logging and user feedback."""
        logger.error(error_message)
        await self._stream_update("error", error_message)
        await self._stream_update("end", timestamp=datetime.now().isoformat())
        
    async def _get_orchestrator_response(self, user_query, user_id, session_id):
        """Get and validate orchestrator response."""
        try:
            orchestrator_response = self.orchestrate_agent(user_query)
            logger.info(f"Orchestrator response received: {orchestrator_response}")
            
            if not orchestrator_response:
                await self._handle_error("Failed to classify the query. Please try rephrasing your question.")
                return None
                
            return orchestrator_response
        except Exception as e:
            await self._handle_error(f"Error getting orchestrator response: {str(e)}")
            return None
            
    async def _execute_single_agent(self, agent_config: Dict, agent_responses: List, 
                                   original_query: str, remaining_plan: List = None, 
                                   current_index: int = 0, is_single_widget: bool = False) -> Dict[str, Any]:
        """
        Execute a single agent and handle its response.
        
        Args:
            agent_config: Configuration for the agent to execute
            agent_responses: List of responses collected so far
            original_query: The original user query
            remaining_plan: The remaining agents in the plan (for approval handling)
            current_index: Current index in the plan (for calculating remaining agents)
            is_single_widget: Whether this is for a single widget generation
            
        Returns:
            Dictionary with execution result and any special handling needed
        """
        agent_name = agent_config["agent_name"].lower()
        step_number = agent_config.get("step_number", 1)
        
        logger.info(f"Executing step {step_number}: {agent_name}")
        
        # Handle user clarification requests
        if agent_name == 'user':
            clarification_msg = agent_config.get('clarification_message', 'Clarification needed')
            await self._stream_update('thinking', clarification_msg)
            agent_responses.append({"agent_name": agent_name, "response": clarification_msg})
            return {
                "status": "clarification_needed",
                "responses": agent_responses
            }
        
        # Execute MCP agents
        elif agent_name in self.mcp_clients:
            enhanced_query = self._build_enhanced_query(original_query, agent_responses)
            response = await self._safe_execute_agent(agent_name, enhanced_query, agent_responses)
            
            if response and response.success:
                json_resp = extract_and_fix_json(response.response)
                if json_resp:
                    self.collected_datasets.append(str(json_resp))
                    self.total_datasets += 1
                agent_responses.append({"agent_name": agent_name, "response": response.response})
                return {
                    "status": "success",
                    "responses": agent_responses
                }
            elif response and isinstance(response.response, dict) and response.response.get('type') == 'tool_approval_needed':
                # Tool approval needed - include remaining plan
                approval_data = response.response
                if remaining_plan:
                    approval_data["remaining_plan"] = remaining_plan[current_index + 1:] if current_index < len(remaining_plan) - 1 else []
                approval_data["original_query"] = original_query
                approval_data["pending_responses"] = agent_responses
                
                # Handle both single interrupt (backward compatibility) and multiple interrupts
                if "interrupts" in approval_data:
                    # Multiple interrupts
                    await self._stream_update(
                        "tool_approval_needed",
                        f"Multiple tool approvals required for {approval_data['agent_name']} ({approval_data.get('total_interrupts', 0)} tools)",
                        extra=approval_data
                    )
                else:
                    # Single interrupt (backward compatibility)
                    await self._stream_update(
                        "tool_approval_needed",
                        f"Tool approval required for {approval_data['agent_name']}",
                        extra=approval_data
                    )
                
                return {
                    "status": "approval_needed",
                    "approval_data": approval_data
                }
            else:
                await self._stream_update('thinking', f"Agent {agent_name} encountered an error: {response}")
                logger.warning(f"Agent {agent_name} failed: {response.error_message if response else 'Unknown error'}")
                return {
                    "status": "agent_failed",
                    "responses": agent_responses,
                    "error": response.error_message if response else 'Unknown error'
                }
        else:
            # Agent not found
            error_msg = f"Agent {agent_name} not found in available agents."
            await self._handle_error(error_msg)
            return {
                "status": "agent_not_found",
                "error": error_msg
            }

    async def _execute_remaining_plan(self, remaining_plan: List, original_query: str, 
                                     current_responses: List) -> Dict[str, Any]:
        """Execute the remaining agents in the orchestrated plan."""
        try:
            logger.info(f"Executing remaining plan with {len(remaining_plan)} agents")
            agent_responses = current_responses.copy()
            
            for idx, agent_config in enumerate(remaining_plan):
                result = await self._execute_single_agent(
                    agent_config, agent_responses, original_query, remaining_plan, idx
                )
                if result["status"] == "clarification_needed":
                    return result["responses"]
                elif result["status"] == "error":
                    return result["error_response"]
                elif result["status"] == "approval_needed":
                    return {
                        "type": "tool_approval_needed",
                        "content": result["approval_data"]
                    }
                elif result["status"] == "success":
                    agent_responses = result["responses"]
                elif result["status"] == "agent_failed":
                    agent_responses = result["responses"]
                    # Continue with other agents instead of breaking
                elif result["status"] == "agent_not_found":
                    return {"type": ResponseType.ERROR.value, "content": result["error"]}
            
            # Process final responses
            return await self._process_final_responses(agent_responses, original_query, False)
            
        except Exception as e:
            logger.error(f"Error executing remaining plan: {e}")
            await self._handle_error(f"Error executing remaining plan: {str(e)}")
            return {"type": ResponseType.ERROR.value, "content": f"Error executing remaining plan: {str(e)}"}

    async def continue_with_tool_approval(self, agent_name: str, query: str, interrupt_ids: list, 
                                        approval_responses: list, pending_responses: List = None,
                                        remaining_plan: List = None, original_query: str = None) -> Optional[str]:
        """Continue agent execution after tool approval and resume the orchestrated plan."""
        try:
            logger.info(f"Executing approved tools for {agent_name} with {len(interrupt_ids)} approvals")
            
            # Check if any user denied the requests
            denied_tools = []
            approved_tools = []
            
            for i, (interrupt_id, approval_response) in enumerate(zip(interrupt_ids, approval_responses)):
                if approval_response.lower() in ['deny', 'n', 'no']:
                    tool_name = self._pending_tool_calls.get(interrupt_id, {}).get('tool_name', 'unknown')
                    denied_tools.append(tool_name)
                else:
                    approved_tools.append(interrupt_id)
            
            if denied_tools:
                denied_msg = f"Tool execution denied by user for: {', '.join(denied_tools)}"
                await self._stream_update("content", denied_msg)
                logger.info(f"Tools denied: {denied_tools}")
                # Continue with remaining plan even if some tools were denied
                if remaining_plan and len(remaining_plan) > 0:
                    return await self._execute_remaining_plan(remaining_plan, original_query or query, pending_responses or [])
                return denied_msg
            
            # Import the approval cache functions
            from .hooks.approval_hooks import set_tool_approval, clear_tool_approval
            
            # Set approvals for all interrupt IDs
            always_approve_tools = []
            for i, (interrupt_id, approval_response) in enumerate(zip(interrupt_ids, approval_responses)):
                # Extract the tool name from the pending tool calls
                tool_name = self._pending_tool_calls.get(interrupt_id, {}).get('tool_name', 'unknown')
                
                # Set the approval for this specific tool
                set_tool_approval(interrupt_id, tool_name, approval_response)
                
                # If user chose "always", also set the specific tool for always approve
                if approval_response.lower() in ["always", "a"]:
                    if tool_name != 'unknown':
                        self.set_tool_always_approve(tool_name)
                        always_approve_tools.append(tool_name)
            
            if always_approve_tools:
                logger.info(f"Tools added to always approve list: {always_approve_tools}")
            
            try:
                # Re-execute the agent with all approvals cached
                query = self._build_enhanced_query(original_query, pending_responses)
                result = await self._execute_agent(agent_name, query)
                if 'pending_responses' in result:
                    pending_responses.extend(result['pending_responses'])
                # Process the result
                agent_responses = pending_responses or []
                
                if isinstance(result, dict) and result.get("type") == "tool_approval_needed":
                    # If we get another approval request, return it with the remaining plan
                    result["remaining_plan"] = remaining_plan
                    result["original_query"] = original_query
                    result["pending_responses"] = agent_responses
                    
                    await self._stream_update(
                    "tool_approval_needed",
                    f"Additional tool approval required for {result['agent_name']}",
                    extra=result)

                    return result
                elif result:
                    # Add this agent's response to the collection
                    json_resp = extract_and_fix_json(result) if isinstance(result, str) else result
                    if json_resp:
                        self.collected_datasets.append(str(json_resp))
                        self.total_datasets += 1
                    agent_responses.append({"agent_name": agent_name, "response": result})
                
                # Continue with the remaining plan if there are more agents to execute
                if remaining_plan and len(remaining_plan) > 0:
                    return await self._execute_remaining_plan(remaining_plan, original_query, agent_responses)
                else:
                    # No more agents in the plan, process final responses
                    return await self._process_final_responses(agent_responses, original_query, False)
                    
            finally:
                # Clean up all temporary approvals
                for interrupt_id in interrupt_ids:
                    clear_tool_approval(interrupt_id)
                    
        except Exception as e:
            logger.error(f"Error continuing agent execution after approval: {e}")
            await self._stream_update("error", f"Error executing approved tools: {str(e)}")
            return None

    async def continue_with_confirmed_plan(self, plan: list, original_query: str, stream_callback, user_id: str = "default", session_id: str="None", is_single_widget=False):
        """Continue processing with a confirmed plan from human."""
        try:
            # Initialize agents and setup
            self.stream_callback = stream_callback
            
            user_query = f"Previous Conversations: \n {self.orchestrate_agent.messages} \n current_query: {original_query}"
            # Conversation tracking variables
            conversation_resolved = False
            accumulated_responses = []
            is_clarification_needed = False
            
            logger.info(f"Executing confirmed plan for user {user_id}, session {session_id}")
            
            # Execute the confirmed plan
            await self._stream_update("thinking", f"\n Executing confirmed plan... {plan} \n")
            
            # Execute each identified agent - FIXED: Properly accumulate responses
            agent_responses = []
            try:
                for idx, agent_config in enumerate(plan):
                    # Pass the accumulated responses to each agent
                    result = await self._execute_single_agent(
                        agent_config, agent_responses.copy(), original_query, plan, idx, is_single_widget
                    )
                    
                    if result["status"] == "clarification_needed":
                        is_clarification_needed = True
                        # Keep all accumulated responses
                        agent_responses.extend(result["responses"])
                        break
                    elif result["status"] == "error":
                        return result["error_response"]
                    elif result["status"] == "approval_needed":
                        return {
                            "type": "tool_approval_needed",
                            "content": result["approval_data"]
                        }
                    elif result["status"] == "success":
                        # FIXED: Accumulate responses instead of overwriting
                        new_responses = result["responses"]
                        # Only add the new response (last one in the list)
                        if new_responses and len(new_responses) > len(agent_responses):
                            agent_responses.extend(new_responses[len(agent_responses):])
                        logger.info(f"Agent {agent_config['agent_name']} completed successfully. Total responses: {len(agent_responses)}")
                    elif result["status"] == "agent_failed":
                        # FIXED: Still accumulate responses even if agent failed
                        new_responses = result["responses"]
                        if new_responses and len(new_responses) > len(agent_responses):
                            agent_responses.extend(new_responses[len(agent_responses):])
                        logger.warning(f"Agent {agent_config['agent_name']} failed but continuing with other agents")
                        # Continue with other agents instead of breaking
                    elif result["status"] == "agent_not_found":
                        await self._handle_error(result["error"])
                        break
                
                # Process final responses with better error handling
                return await self._process_final_responses(agent_responses, user_query, is_clarification_needed)
                
            except Exception as e:
                logger.error(f"Error executing confirmed plan: {e}")
                await self._handle_error(f"Error executing plan: {str(e)}")
                return {"type": ResponseType.ERROR.value, "content": f"Error executing plan: {str(e)}"}
                
        except Exception as e:
            logger.error(f"Error in continue_with_confirmed_plan: {e}")
            await self._stream_update("error", f"Failed to execute confirmed plan: {str(e)}")
            return {
                "type": ResponseType.ERROR.value,
                "content": f"Plan execution failed: {str(e)}"
            }
    
    async def _safe_execute_agent(self, agent_name: str, user_query: str, agent_responses: List[Dict]) -> Optional[AgentResponse]:
        """Safely execute an agent with proper error handling."""
        try:
            # Build enhanced query with context
            updated_query = self._build_enhanced_query(user_query, agent_responses)
            
            # Execute agent
            response = await self._execute_agent(agent_name, updated_query)
            
            # Check if we got an approval request instead of a normal response
            if isinstance(response, dict) and response.get("type") == "tool_approval_needed":
                # Handle both single interrupt (backward compatibility) and multiple interrupts
                if "interrupts" in response:
                    # Multiple interrupts - new format
                    await self._stream_update(
                        "tool_approval_needed",
                        f"Multiple tool approvals required for {agent_name} ({response.get('total_interrupts', 0)} tools)",
                        extra={
                            "interrupts": response["interrupts"],
                            "agent_name": response["agent_name"],
                            "query": response["query"],
                            "pending_responses": response.get("pending_responses", []),
                            "total_interrupts": response.get("total_interrupts", 0),
                            "auto_approved_count": response.get("auto_approved_count", 0)
                        }
                    )
                else:
                    # Single interrupt - backward compatibility
                    await self._stream_update(
                        "tool_approval_needed",
                        f"Tool approval required for {agent_name}",
                        extra={
                            "interrupt_id": response.get("interrupt_id"),
                            "reason": response.get("reason"),
                            "agent_name": response["agent_name"],
                            "query": response["query"],
                            "pending_responses": response.get("pending_responses", [])
                        }
                    )
                
                # Return a special response indicating approval is needed
                return AgentResponse(
                    agent_name, 
                    response, 
                    False, 
                    "Tool approval required",
                    {"approval_needed": True}
                )
            
            if response:
                return AgentResponse(agent_name, response, True)
            else:
                return AgentResponse(agent_name, "", False, "No response received")
                
        except Exception as e:
            logger.error(f"Error executing agent {agent_name}: {e}")
            return AgentResponse(agent_name, "", False, str(e))
    
    def _build_enhanced_query(self, user_query: str, agent_responses: List[Dict]) -> str:
        """Build enhanced query with context from previous responses."""
        return PromptTemplates.get_enhanced_query_with_context(user_query, agent_responses)
    
    async def _process_final_responses(self, agent_responses: List[Dict], user_query: str, is_clarification_needed: bool) -> Dict[str, Any]:
        """Process final responses with improved error handling."""
        try:
            # Check if any agent requires approval
            for response in agent_responses:
                if (hasattr(response, 'get') and 
                    isinstance(response.get('response'), dict) and 
                    response['response'].get('type') == 'tool_approval_needed'):
                    
                    approval_data = response['response']
                    await self._stream_update(
                        "tool_approval_needed",
                        f"Tool approval required for {approval_data['agent_name']}",
                        extra=approval_data
                    )
                    
                    return {
                        "type": "tool_approval_needed",
                        "content": approval_data
                    }
            
            if agent_responses:
                # Combine all agent responses
                combined_response = "\n\n".join([
                    f"**{resp['agent_name']} Response:**\n{resp['response']}"
                    for resp in agent_responses
                    if not (isinstance(resp.get('response'), dict) and 
                           resp['response'].get('type') == 'tool_approval_needed')
                ])

                if is_clarification_needed:
                    await self._stream_update("content", combined_response, is_partial=False)
                    return {"type": ResponseType.CLARIFICATION.value, "content": combined_response}
                
                # Evaluate if the query is resolved with better error handling
                try:
                    verifier_input = f"User Query: {user_query}. Agent Responses: {combined_response}"
                    verifier_response = self.orchestrate_agent("Assume the verifier role and let us know if this data is sufficient to answer the user query: " + verifier_input)

                    # Parse the verifier response with improved error handling
                    verifier_response_str = extract_and_fix_json(str(verifier_response))
                    
                    if verifier_response_str and 'tool_error' in verifier_response_str:
                        tool_error = get_json_key(verifier_response_str, "tool_error")
                        if tool_error == "yes":
                            tool_name = get_json_key(verifier_response_str, "tool_name")
                            if tool_name:
                                await self._stream_update("content", f"Repeated errors when calling tool {tool_name}. Please reach out to System Administrator")
                                return {"type": ResponseType.ERROR.value, "content": f"Repeated errors when calling tool {tool_name}"}
                            else:
                                await self._stream_update("content", "Tool errors detected. Please reach out to System Administrator")
                                return {"type": ResponseType.ERROR.value, "content": "Tool errors detected"}
                    
                    can_answer = get_json_key(verifier_response_str, "can_answer") if verifier_response_str else None
                    if can_answer == 'yes':
                        # Generate business analysis report
                        summarize_response = quick_summarize(verifier_input, "", self.config.model.cheaper_model_id)
                        
                        # Send summary with citations (raw data)
                        await self._stream_update(
                            "with_citations",
                            summarize_response,
                            is_partial=False,
                            extra={
                                "citations": combined_response,  # Raw data as citations
                                "query": user_query,
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                        
                        return summarize_response
                    else:
                        # If the plan was approved but didn't resolve the query
                        await self._stream_update(
                            "content", 
                            f"The approved plan didn't fully resolve your query. Here's what we found:\n\n{combined_response}\n\nYou may want to try a different approach or provide more details.", 
                            is_partial=False
                        )
                        return {"type": ResponseType.PARTIAL.value, "content": combined_response}
                        
                except Exception as e:
                    logger.error(f"Error in verification step: {e}")
                    # Fallback to basic evaluation
                    await self._stream_update("content", combined_response, is_partial=False)
                    return {"type": ResponseType.SUCCESS.value, "content": combined_response}
            else:
                await self._handle_error("No agents were able to process your query. Please try rephrasing.")
                return {"type": ResponseType.ERROR.value, "content": "No agents were able to process your query"}
                
        except Exception as e:
            logger.error(f"Error processing final responses: {e}")
            await self._handle_error(f"Error processing responses: {str(e)}")
            return {"type": ResponseType.ERROR.value, "content": f"Error processing responses: {str(e)}"}
    
    async def process_message_stream(
        self, message: str, stream_callback, user_id: str = "default", session_id: str="None", is_single_widget=False):
        """Process a message with streaming callback for real-time updates."""
        
        try:
            # Initialize agents and setup
            self.stream_callback = stream_callback
            user_query = message
            
            # Ensure all agents are created
            if not self.orchestrate_agent or not self.verifier_agent:
                logger.info("Creating agents for session")
                self.create_all_agents(user_id=user_id, session_id=session_id)
            
            # Conversation tracking variables using config
            conversation_resolved = False
            max_iterations = self.config.processing.max_iterations
            iteration_count = 0
            logger.info(f"Processing message stream for user {user_id}, session {session_id}")
            
            # Main conversation loop
            while not conversation_resolved and iteration_count < max_iterations:
                iteration_count += 1
                await self._stream_update("thinking", f"\n Calling Multi-Agent Router, times={iteration_count} ... ")
                logger.info(f"Starting iteration {iteration_count}")
                
                # Step 1: Get orchestrator response
                additional_prompts = user_query
                if iteration_count > 1:
                    additional_prompts = f"Previous plan didnt work. Try a new plan to solve the query. Original User query: {user_query}"
                orchestrator_response = await self._get_orchestrator_response(user_query=additional_prompts, user_id=user_id, session_id=session_id)
                if not orchestrator_response:
                    break
                # Parse orchestrator response
                orchestrator_response_str = str(orchestrator_response)
                if "[" in orchestrator_response_str and "]" in orchestrator_response_str:
                    # Extract the JSON part between brackets
                    start_bracket = orchestrator_response_str.split("[")[1]
                    json_part = start_bracket.split("]")[0]
                    json_response = json.loads("[" + json_part + "]")
                    
                    # Human in the loop confirmation (configurable)
                    if self.config.processing.require_human_confirmation:
                        await self._stream_update("thinking", f"Orchestrator has prepared a plan. Waiting for human confirmation... \n {json_response}")
                        extras = {
                            "plan": json_response,
                            "original_query": user_query
                        }
                        await self._stream_update("confirmation_needed", extra=extras, is_partial=False)
                        
                        # Wait for human confirmation (this would need to be implemented in the frontend)
                        # For now, we'll return and let the frontend handle the confirmation flow
                        return {
                            "type": "confirmation_needed",
                            "plan": json_response,
                            "original_query": user_query
                        }
                    else:
                        # Auto-execute without confirmation
                        return await self.continue_with_confirmed_plan(
                            json_response, user_query, stream_callback, user_id, session_id, is_single_widget
                        )
                else: 
                    await self._stream_update("content", orchestrator_response_str, is_partial=False)
                    return
                

            # If we hit max iterations, inform the user
            if iteration_count >= max_iterations and not conversation_resolved:
                await self._stream_update(
                    "content",
                    f"Maximum iterations ({max_iterations}) reached. This query cant be resolved."
                )
                await self._stream_update("end", timestamp=datetime.now().isoformat())
                

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self._stream_update("content", f"Sorry, I encountered an error: {str(e)}", is_partial=False)

    def stop(self):
        """Stop the chatbot."""
        self.is_running = False
        
        # Cancel health check task
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            logger.info("Health check task cancelled")
        
        print("🛑 Stopping chatbot...")

    async def _health_check_loop(self):
        """Periodic health check loop for MCP connections."""
        logger.info("Starting health check loop")
        
        while self.is_running:
            try:
                await asyncio.sleep(self._health_check_interval)
                if not self.is_running:
                    break
                    
                await self._check_mcp_connections()
                
            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _check_mcp_connections(self):
        """Check health of all MCP connections and reconnect if needed."""
        logger.debug("Checking MCP connection health")
        
        for mcp_name, mcp_config in self.mcp_clients.items():
            try:
                # Test connection by trying to list tools
                is_healthy = await self._test_mcp_connection(mcp_name)
                
                if not is_healthy:
                    logger.warning(f"MCP connection {mcp_name} is unhealthy, attempting reconnection")
                    await self._reconnect_mcp_client(mcp_name, mcp_config)
                else:
                    # Reset reconnection attempts on successful health check
                    self._reconnection_attempts[mcp_name] = 0
                    
            except Exception as e:
                logger.error(f"Error checking health for {mcp_name}: {e}")

    async def _test_mcp_connection(self, mcp_name: str) -> bool:
        """Test if an MCP connection is healthy."""
        try:
            mcp_client = self.get_mcp_client(mcp_name)
            if not mcp_client:
                return False
                
            # Test connection with a timeout
            with mcp_client:
                # Try to list tools as a health check
                tools = mcp_client.list_tools_sync()
                return len(tools) >= 0  # Even 0 tools is a valid response
                
        except Exception as e:
            logger.debug(f"Health check failed for {mcp_name}: {e}")
            return False

    async def _reconnect_mcp_client(self, mcp_name: str, mcp_config: dict):
        """Attempt to reconnect a failed MCP client."""
        # Track reconnection attempts
        attempts = self._reconnection_attempts.get(mcp_name, 0)
        
        if attempts >= self._max_reconnection_attempts:
            logger.error(f"Max reconnection attempts reached for {mcp_name}")
            return False
            
        self._reconnection_attempts[mcp_name] = attempts + 1
        
        try:
            logger.info(f"Reconnecting {mcp_name} (attempt {attempts + 1}/{self._max_reconnection_attempts})")
            
            # Exponential backoff
            backoff_delay = min(2 ** attempts, 30)  # Max 30 seconds
            await asyncio.sleep(backoff_delay)
            
            # Create MCP client using existing config
            mcp_client = self._create_mcp_client(mcp_config)
            
            # Test the new connection
            with mcp_client:
                tools = mcp_client.list_tools_sync()
                logger.info(f"Successfully reconnected {mcp_name} with {len(tools)} tools")
                
                # Update tool config
                tool_config = []
                for tool in tools:
                    tool_config.append({
                        "name": tool.tool_name,
                        "description": tool.tool_spec["description"],
                        "inputSchema": tool.tool_spec["inputSchema"],
                    })
                
                # Update the stored config with all original parameters preserved
                self.mcp_clients[mcp_name.lower()] = self._preserve_server_config(
                    mcp_name, mcp_config, tool_config, is_reconnection=True
                )
                
                # Reset reconnection attempts on success
                self._reconnection_attempts[mcp_name] = 0
                return True
                    
        except Exception as e:
            logger.error(f"Failed to reconnect {mcp_name}: {e}")
            
        return False

    async def retry_failed_initialization(self, mcp_name: str):
        """Retry initialization of a server that failed to initialize."""
        if mcp_name not in self.sse_urls:
            logger.error(f"Server {mcp_name} not found in configuration")
            return False
            
        server_config = self.sse_urls[mcp_name]
        
        # Skip if disabled
        if server_config.get("disabled", False):
            logger.info(f"Skipping disabled server: {mcp_name}")
            return False
            
        logger.info(f"Retrying initialization for {mcp_name}")
        
        # Reset reconnection attempts
        self._reconnection_attempts[mcp_name] = 0
        
        # Use the unified initialization method
        return await self._initialize_mcp_client(mcp_name, server_config)

    async def get_all_server_status(self) -> dict:
        """Get status of all configured servers, including uninitialized ones."""
        status = {}
        
        # First, add all configured servers
        for server_key, server_config in self.sse_urls.items():
            server_name = server_config.get("name", str(server_key).capitalize())
            status[server_name] = {
                "configured": True,
                "initialized": server_name in self.mcp_clients,
                "connected": False,
                "reconnection_attempts": self._reconnection_attempts.get(server_name, 0),
                "max_attempts_reached": self._reconnection_attempts.get(server_name, 0) >= self._max_reconnection_attempts,
                "disabled": server_config.get("disabled", False)
            }
        
        # Then update with actual connection status for initialized clients
        for mcp_name in self.mcp_clients.keys():
            is_healthy = await self._test_mcp_connection(mcp_name)
            attempts = self._reconnection_attempts.get(mcp_name, 0)
            
            if mcp_name in status:
                status[mcp_name].update({
                    "connected": is_healthy,
                    "reconnection_attempts": attempts,
                    "max_attempts_reached": attempts >= self._max_reconnection_attempts
                })
            
        return status

    async def get_connection_status(self) -> dict:
        """Get the current connection status of all MCP clients."""
        status = {}
        
        for mcp_name in self.mcp_clients.keys():
            is_healthy = await self._test_mcp_connection(mcp_name)
            attempts = self._reconnection_attempts.get(mcp_name, 0)
            
            status[mcp_name] = {
                "connected": is_healthy,
                "reconnection_attempts": attempts,
                "max_attempts_reached": attempts >= self._max_reconnection_attempts
            }
            
        return status

    async def _execute_agent(self, agent_name: str, query: str) -> Optional[str]:
        """Execute a specific agent and return its response, handling interrupts."""
        try:
            mcp_client = self.get_mcp_client(agent_name)
            if not mcp_client:
                logger.error(f"MCP client not found for agent: {agent_name}")
                return None
                
            with mcp_client:
                tools = mcp_client.list_tools_sync()
                agent = self.agent_builder(
                    agent_name, 
                    self.mcp_clients[agent_name]["rules_prompt"], 
                    tools, 
                    self.mcp_clients[agent_name]["tools"]
                )
                
                # Execute agent with interrupt handling
                # response_stream = agent.stream_async(query)
                # result = ""
                # async for chunk in response_stream:
                #     result += await self.callback_handler(chunk)
                
                result = agent(query)
                tool_execution_details = []
                agent_resp = None
                if hasattr(result, 'message') and result.message:
                    # Fix: Access message attribute properly, not as dictionary
                    if 'content' in result.message and result.message['content']:
                        for payload in result.message['content']:
                            if 'toolUse' in payload:
                                tool_execution_details.append(f"Execute Tool_Name: {payload['toolUse']['name']} with Tool_Input: {payload['toolUse']['input']}")
                            if 'text' in payload:
                                agent_resp = payload['text']
                
                # Handle interrupts if they occur
                while result.stop_reason == "interrupt":
                    responses = []
                    agent_msg = f"""Agent {agent_name} Execution Details {agent_resp}.{tool_execution_details}"""
                    responses.append({"agent_name": agent_name, "response": agent_msg})
                    
                    # Collect all interrupts that need user approval
                    pending_interrupts = []
                    auto_approved_count = 0
                    
                    for interrupt in result.interrupts:
                        if interrupt.name.endswith("-tool-approval"):
                            # Check if this tool has been marked for "always approve"
                            tool_name = interrupt.reason.get('tool_name', '')
                            approval_key = f"{agent_name}-{tool_name}-approval"
                            
                            # Check agent's session state for "always" approvals
                            if agent.state.get(approval_key) == "approved":
                                logger.info(f"Tool {tool_name} has 'always approve' status, continuing execution")
                                # Continue execution without interrupting the user
                                interrupt.respond("always")
                                auto_approved_count += 1
                                continue
                            
                            # Check global approval cache for temporary "always" approvals
                            from .hooks.approval_hooks import _approval_cache
                            auto_approved = False
                            
                            for cache_interrupt_id, approval_data in list(_approval_cache.items()):
                                # Check if this is an "always" approval for this specific tool or "any" tool
                                if (approval_data.get('tool_name') in [tool_name, "any"] and 
                                    approval_data.get('response', '').lower() in ["always", "a"]):
                                    logger.info(f"Found 'always approve' cache entry for tool {tool_name}")
                                    # Store in session state for future calls
                                    agent.state.set(approval_key, "approved")
                                    # Continue execution without interrupting the user
                                    interrupt.respond("always")
                                    auto_approved = True
                                    auto_approved_count += 1
                                    break
                            
                            if not auto_approved:
                                # Add to pending interrupts list
                                pending_interrupts.append(interrupt)
                    
                    # If we have interrupts that need user approval, return them all
                    if pending_interrupts:
                        logger.info(f"Found {len(pending_interrupts)} interrupts requiring approval, {auto_approved_count} auto-approved")
                        
                        # Stream approval requests for all pending interrupts
                        interrupt_data = []
                        for interrupt in pending_interrupts:
                            await self._stream_approval_request(interrupt)
                            
                            # Store interrupt data
                            interrupt_info = {
                                "interrupt_id": interrupt.id,
                                "reason": interrupt.reason,
                                "tool_name": interrupt.reason.get('tool_name', 'Unknown'),
                                "risk_level": interrupt.reason.get('risk_level', 'Unknown'),
                                "summary": interrupt.reason.get('summary', 'No summary available'),
                                "details": interrupt.reason.get('details', {})
                            }
                            interrupt_data.append(interrupt_info)
                        
                        # Return all interrupts to be handled by the UI
                        return {
                            "type": "tool_approval_needed",
                            "interrupts": interrupt_data,  # Changed from single interrupt to list
                            "agent_name": agent_name,
                            "query": query,
                            "pending_responses": responses,
                            "total_interrupts": len(pending_interrupts),
                            "auto_approved_count": auto_approved_count
                        }
                    
                    # If all interrupts were auto-approved, continue execution
                    if auto_approved_count > 0:
                        logger.info(f"All {auto_approved_count} interrupts were auto-approved, continuing execution")
                        # Continue to next iteration or completion
                        break
                    
                    # This should not be reached, but kept for safety
                    break
                
                # Process the final result
                if hasattr(result, 'message') and result.message:
                    return result.message
                else:
                    return str(result)
                    
        except Exception as e:
            logger.error(f"Error executing agent {agent_name}: {e}")
            return None
            
    async def _stream_approval_request(self, interrupt):
        """Stream approval request to the user interface."""
        reason = interrupt.reason
        
        # Store the tool call information for later execution
        if not hasattr(self, '_pending_tool_calls'):
            self._pending_tool_calls = {}
            
        # Extract tool information from the interrupt reason
        tool_name = reason.get('tool_name', 'Unknown')
        tool_input = reason.get('tool_input', {})  # Get the actual tool input parameters
        
        # Store the tool call info using the interrupt ID
        self._pending_tool_calls[interrupt.id] = {
            'tool_name': tool_name,
            'tool_input': tool_input,
            'reason': reason
        }
        
        logger.info(f"Stored tool call info for interrupt {interrupt.id}: {tool_name} with input: {tool_input}")
        
        # Note: We don't stream individual approval messages here anymore
        # The consolidated approval request will be streamed from _execute_agent

    async def _generate_business_analysis_report(self, combined_response: str, user_query: str) -> Dict[str, Any]:
        """Generate business analysis report with error handling."""
        try:
            # Use the response summarizer utility to generate the HTML report
            html_content = self.response_summarizer.generate_business_analysis_report(
                data=combined_response,
                user_query=user_query
            )

            try:
                # Save the report to file using relative path
                current_file = pathlib.Path(__file__)
                project_root = current_file.parent.parent.parent
                report_dir = project_root / "generated_reports"
                report_dir.mkdir(exist_ok=True, parents=True)
                
                # Generate a unique filename based on timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_title = "Data_Analysis_Report"
                
                # Extract title from HTML if possible
                if '<title>' in html_content and '</title>' in html_content:
                    report_title = html_content.split('<title>')[1].split('</title>')[0].replace(' ', '_')
                
                filename = f"{report_title}_{timestamp}.html"
                filepath = report_dir / filename
                
                # Save the HTML report to file
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)
            except Exception as e:
                logger.error(f"Error saving generated report {e}")

            # Send the HTML content to the frontend with citations
            await self._stream_update(
                "html_content",
                html_content,
                is_partial=False,
                metadata={
                    "generated_at": datetime.now().isoformat(),
                    "query": user_query
                },
                title="Data Analysis Report"
            )
            
            # Also provide a text summary for non-HTML clients
            await self._stream_update(
                "content",
                "I've analyzed the data and created a detailed HTML report with visualizations. You can view it above.",
                is_partial=False
            )
            
            return {"type": ResponseType.HTML_CONTENT.value, "content": html_content}
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            await self._stream_update(
                "content",
                f"I've analyzed the data but encountered an error generating the HTML report: {str(e)}. Here's a text summary instead:\n\n{combined_response}",
                is_partial=False
            )
            return {"type": ResponseType.ERROR.value, "content": f"Error generating HTML report: {str(e)}"}