from mcp import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.client.sse import sse_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder
from strands.session.file_session_manager import FileSessionManager
import asyncio
import json
import logging
from datetime import datetime
import uuid
from typing import Optional, Dict, Any, List
import pathlib
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
from utils.models import ResponseType, AgentResponse
from utils.json_utils import extract_and_fix_json, get_json_key

def setup_logging(config: ChatbotConfig):
    """Setup logging based on configuration."""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    # Create logs directory in project root if it doesn't exist
    current_file = pathlib.Path(__file__)
    project_root = current_file.parent.parent.parent
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True, parents=True)
    
    log_file_path = logs_dir / "graph_mcp_chatbot.log"
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_file_path))
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    return logger

# Initialize with default config
logger = setup_logging(DEFAULT_CONFIG)

class GraphMCPChatbot:
    """
    Graph-based MCP chatbot using StrandsSDK GraphBuilder.
    
    This implementation uses a graph structure where:
    - Orchestrator is the entry point that decides which specialists to call
    - Specialists execute MCP tools and return results
    - Verifier checks if the query is resolved
    - If verifier says "can_answer: no", it loops back to orchestrator for replanning
    - If verifier says "can_answer: yes", ResponseSummarizer provides the final response
    """

    def __init__(
        self,
        sse_urls: dict = {},
        stream_callback=None,
        config: ChatbotConfig = None,
    ):
        """Initialize the Graph MCP Chatbot."""
        self.sse_urls = sse_urls
        self.is_running = False
        self.stream_callback = stream_callback
        self.mcp_clients = {}
        self._health_check_task = None
        self._health_check_interval = 30
        self._reconnection_attempts = {}
        self._max_reconnection_attempts = 3
        
        # Use provided config or default
        self.config = config or DEFAULT_CONFIG
        
        # Initialize models using config
        self.model = BedrockModel(model_id=self.config.model.primary_model_id)
        self.cheaper_model = BedrockModel(model_id=self.config.model.cheaper_model_id)
        
        # Graph components
        self.graph = None
        self.session_manager = None
        self.response_summarizer = None
        
        # State tracking
        self.collected_datasets = []
        self.total_datasets = 0
        self.original_query = None
        self.current_user_id = None
        self.current_session_id = None

    async def start(self):
        """Start the chatbot and initialize all components."""
        try:
            self.is_running = True
            print("🤖 Starting Graph-based MCP Chatbot...")
            print("=" * 50)
            logger.info("Starting Graph MCP Chatbot")
            
            # Initialize MCP clients
            for mcp_name, server_config in self.sse_urls.items():
                if server_config.get("disabled", False):
                    logger.info(f"Skipping disabled MCP server: {mcp_name}")
                    continue
                    
                success = await self._initialize_mcp_client(mcp_name, server_config)
                if success:
                    print(f"🛠️ Initialized {mcp_name} MCP client")
                else:
                    print(f"❌ Failed to initialize {mcp_name} MCP client")
            
            print("✅ Graph MCP Chatbot started successfully")
            print("🎯 Chatbot is ready to process requests via API!")
            print("=" * 50)
            
            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            logger.info("Graph MCP Chatbot started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting chatbot: {e}")
            print(f"❌ Failed to start chatbot: {e}")
            self.is_running = False
            raise e

    def _create_session_manager(self, user_id: str, session_id: str):
        """Create session manager for the graph."""
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent.parent
        sessions_dir = project_root / "multiagent_sessions"
        sessions_dir.mkdir(exist_ok=True, parents=True)
        
        session_key = f"{user_id}_{session_id}_{uuid.uuid4()}"
        return FileSessionManager(session_id=session_key, storage_dir=str(sessions_dir))

    def _create_orchestrator_agent(self) -> Agent:
        """Create the orchestrator agent that decides which specialists to call."""
        available_agents = list(self.mcp_clients.values())
        orchestrator_prompt = PromptTemplates.get_orchestrator_agent_prompt(
            available_agents, 
            self.config.processing.max_iterations
        )
        
        return Agent(
            name="orchestrator",
            model=self.model,
            system_prompt=orchestrator_prompt,
            tools=[self.get_all_available_tools]
        )

    def _create_specialist_agent(self, mcp_name: str) -> Agent:
        """Create a specialist agent for a specific MCP client."""
        mcp_config = self.mcp_clients[mcp_name]
        
        # Get MCP client and tools
        mcp_client = self._create_mcp_client(mcp_config)
        with mcp_client:
            tools = mcp_client.list_tools_sync()
        
        # Create specialized agent prompt
        specialized_prompt = PromptTemplates.get_specialized_agent_prompt().format(
            placeholder=str(mcp_config["tools"]), 
            agent_special_rules=f"2. Rules: {mcp_config['rules_prompt']}"
        )
        
        # Add original query context
        if self.original_query:
            specialized_prompt = f"""{specialized_prompt}
            User Query: {self.original_query}
            """
        
        # Create approval hook for this agent
        approval_hook = MCPToolApprovalHook(
            app_name=f"{mcp_name}_agent",
            tools_requiring_approval=None,
            auto_approve_patterns=None
        )
        
        return Agent(
            name=mcp_name,
            model=self.model,
            system_prompt=specialized_prompt,
            tools=tools,
            hooks=[approval_hook]
        )

    def _create_verifier_agent(self) -> Agent:
        """Create the verifier agent to check if query is resolved."""
        verifier_prompt = PromptTemplates.get_verifier_agent_prompt()
        
        return Agent(
            name="verifier",
            model=self.model,
            system_prompt=verifier_prompt
        )

    def _create_response_summarizer_agent(self) -> Agent:
        """Create the response summarizer agent for final response using ResponseSummarizer."""
        from utils.response_summarizer import ResponseSummarizer
        
        # Get the model ID from the cheaper_model
        # BedrockModel might store the model_id differently, let's use the config directly
        model_id = self.config.model.cheaper_model_id
        
        # Create ResponseSummarizer instance
        summarizer = ResponseSummarizer(model_id=model_id)
        
        # Return the underlying agent with proper configuration
        agent = summarizer.agent
        agent.name = "response_summarizer"
        
        # Override the system prompt to match our graph context
        agent.system_prompt = """You are a content summarization specialist working in a multi-agent data discovery system.
        You excel at:
        - Creating concise summaries from collected data
        - Extracting key insights from specialist agent responses
        - Organizing information clearly for end users
        - Presenting complex data analysis results simply
        
        You will receive collected data from specialist agents and create a comprehensive response to the user's query.
        Be thorough but concise in your analysis. Focus on actionable insights and clear explanations."""
        
        return agent

    def _build_graph(self) -> Any:
        """Build the graph structure for orchestrator-specialist execution."""
        builder = GraphBuilder()
        
        # Create and add orchestrator
        orchestrator = self._create_orchestrator_agent()
        builder.add_node(orchestrator, "orchestrator")
        
        # Create and add specialist agents for each MCP client
        for mcp_name in self.mcp_clients.keys():
            specialist = self._create_specialist_agent(mcp_name)
            builder.add_node(specialist, mcp_name)
            
            # Add conditional edge from orchestrator to specialist
            builder.add_edge(
                "orchestrator", 
                mcp_name, 
                condition=lambda state, name=mcp_name: self._should_call_specialist(state, name)
            )
            
            # Add edge from specialist back to orchestrator for next decision
            builder.add_edge(mcp_name, "orchestrator")
        
        # Create and add verifier
        verifier = self._create_verifier_agent()
        builder.add_node(verifier, "verifier")
        builder.add_edge("orchestrator", "verifier", 
                        condition=lambda state: self._should_verify(state))
        
        # Create and add response summarizer
        response_summarizer = self._create_response_summarizer_agent()
        builder.add_node(response_summarizer, "response_summarizer")
        builder.add_edge("verifier", "response_summarizer",
                        condition=lambda state: self._should_aggregate(state))
        
        # Add feedback loop: verifier back to orchestrator when can't answer
        builder.add_edge("verifier", "orchestrator",
                        condition=lambda state: self._should_replan(state))
        
        # Set orchestrator as entry point
        builder.set_entry_point("orchestrator")
        
        # Configure execution limits
        builder.set_execution_timeout(600)  # 10 minutes
        builder.set_max_node_executions(self.config.processing.max_iterations * 2)
        builder.set_node_timeout(120)  # 2 minutes per node
        builder.set_session_manager(self.session_manager)
        
        return builder.build()

    def _should_call_specialist(self, state, specialist_name: str) -> bool:
        """Determine if orchestrator decided to call this specialist."""
        orchestrator_result = state.results.get("orchestrator")
        if not orchestrator_result:
            return False
        
        result_text = str(orchestrator_result.result).lower()
        
        # Check if the specialist name appears in the orchestrator's decision
        # Look for JSON format with agent_name
        try:
            if "[" in result_text and "]" in result_text:
                start_bracket = result_text.split("[")[1]
                json_part = start_bracket.split("]")[0]
                json_response = json.loads("[" + json_part + "]")
                
                for item in json_response:
                    if isinstance(item, dict) and item.get("agent_name", "").lower() == specialist_name.lower():
                        return True
        except:
            pass
        
        # Fallback: check if specialist name is mentioned
        return specialist_name.lower() in result_text

    def _should_verify(self, state) -> bool:
        """Determine if we should verify the query resolution."""
        # Check if we have collected some data from specialists
        specialist_results = [
            result for node_name, result in state.results.items() 
            if node_name in self.mcp_clients and node_name != "orchestrator"
        ]
        
        # Always verify if we have specialist results
        if specialist_results:
            return True
            
        # Also check if orchestrator suggests we should verify
        orchestrator_result = state.results.get("orchestrator")
        if orchestrator_result:
            result_text = str(orchestrator_result.result).lower()
            # Look for verification keywords or if orchestrator thinks we have enough data
            return any(keyword in result_text for keyword in ["verify", "check", "enough", "sufficient", "complete"])
            
        return False

    def _should_aggregate(self, state) -> bool:
        """Determine if we should aggregate and provide final response."""
        verifier_result = state.results.get("verifier")
        if not verifier_result:
            return False
        
        # Parse verifier response to check if query can be answered
        verifier_response_str = extract_and_fix_json(str(verifier_result.result))
        if verifier_response_str:
            can_answer = get_json_key(verifier_response_str, "can_answer")
            if can_answer == "yes":
                logger.info("✅ Verifier confirmed query can be answered - proceeding to response summarizer")
                return True
        
        return False

    def _should_replan(self, state) -> bool:
        """Determine if we should go back to orchestrator for replanning."""
        verifier_result = state.results.get("verifier")
        if not verifier_result:
            return False
        
        # Parse verifier response to check if query can be answered
        verifier_response_str = extract_and_fix_json(str(verifier_result.result))
        if verifier_response_str:
            can_answer = get_json_key(verifier_response_str, "can_answer")
            if can_answer == "no":
                logger.info("🔄 Verifier determined query cannot be answered - triggering replanning")
                return True
        
        return False

    async def process_message_stream(
        self, message: str, stream_callback, user_id: str = "default", session_id: str = "None"
    ):
        """Process a message using the graph-based execution."""
        try:
            # Setup for this session
            self.stream_callback = stream_callback
            self.original_query = message
            self.current_user_id = user_id
            self.current_session_id = session_id
            
            # Create session manager and response summarizer
            self.session_manager = self._create_session_manager(user_id, session_id)
            self.response_summarizer = ResponseSummarizer(model_id=self.config.model.cheaper_model_id)
            
            # Reset state
            self.collected_datasets = []
            self.total_datasets = 0
            
            logger.info(f"Processing message with graph execution for user {user_id}, session {session_id}")
            
            # Build the graph
            await self._stream_update("thinking", "Building execution graph...")
            self.graph = self._build_graph()
            
            # Execute the graph
            await self._stream_update("thinking", "Starting graph execution...")
            
            # Check if human confirmation is required
            if self.config.processing.require_human_confirmation:
                # First, get the orchestrator's plan
                orchestrator = self._create_orchestrator_agent()
                orchestrator_response = orchestrator(message)
                
                # Parse and present plan for confirmation
                plan = self._extract_plan_from_response(str(orchestrator_response))
                if plan:
                    await self._stream_update("thinking", f"Orchestrator has prepared a plan: {plan}")
                    await self._stream_update("confirmation_needed", extra={
                        "plan": plan,
                        "original_query": message
                    }, is_partial=False)
                    
                    return {
                        "type": "confirmation_needed",
                        "plan": plan,
                        "original_query": message
                    }
            
            # Execute the graph
            result = await self._execute_graph_with_streaming(message)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self._stream_update("error", f"Error processing message: {str(e)}")
            return {"type": ResponseType.ERROR.value, "content": f"Error: {str(e)}"}

    async def continue_with_confirmed_plan(
        self, plan: list, original_query: str, stream_callback, user_id: str = "default", session_id: str = "None"
    ):
        """Continue processing with a confirmed plan."""
        try:
            # Setup for this session
            self.stream_callback = stream_callback
            self.original_query = original_query
            self.current_user_id = user_id
            self.current_session_id = session_id
            
            # Create session manager and response summarizer
            self.session_manager = self._create_session_manager(user_id, session_id)
            self.response_summarizer = ResponseSummarizer(model_id=self.config.model.cheaper_model_id)
            
            logger.info(f"Executing confirmed plan for user {user_id}, session {session_id}")
            
            # Build and execute the graph
            await self._stream_update("thinking", "Executing confirmed plan...")
            self.graph = self._build_graph()
            
            result = await self._execute_graph_with_streaming(original_query)
            return result
            
        except Exception as e:
            logger.error(f"Error executing confirmed plan: {e}")
            await self._stream_update("error", f"Error executing plan: {str(e)}")
            return {"type": ResponseType.ERROR.value, "content": f"Error: {str(e)}"}

    async def _execute_graph_with_streaming(self, query: str):
        """Execute the graph with streaming updates."""
        try:
            await self._stream_update("thinking", "Starting graph execution...")
            
            # Create a custom callback for node execution
            async def node_callback(node_name: str, result: Any):
                """Callback for when a node completes execution."""
                await self._stream_update("thinking", f"Agent {node_name} completed execution")
                
                # If it's a specialist agent, collect the data
                if node_name in self.mcp_clients:
                    json_resp = extract_and_fix_json(str(result))
                    if json_resp:
                        self.collected_datasets.append(str(json_resp))
                        self.total_datasets += 1
                        await self._stream_update("thinking", f"Collected data from {node_name}")
            
            # Execute the graph
            await self._stream_update("thinking", "Executing orchestrator and specialist agents...")
            result = self.graph(query)
            
            # Process the results
            if result.status == "completed":
                await self._stream_update("thinking", "Graph execution completed successfully")
                
                # Extract final response from aggregator or last executed node
                final_output = self._extract_final_output(result)
                
                # Stream the final response
                if self.collected_datasets:
                    combined_data = "\n\n".join([
                        f"**Dataset {idx + 1}:**\n{dataset}"
                        for idx, dataset in enumerate(self.collected_datasets)
                    ])
                    
                    await self._stream_update(
                        "with_citations",
                        final_output,
                        is_partial=False,
                        extra={
                            "citations": combined_data,
                            "query": query,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                else:
                    await self._stream_update("content", final_output, is_partial=False)
                
                return {"type": ResponseType.SUCCESS.value, "content": final_output}
            else:
                error_msg = f"Graph execution failed with status: {result.status}"
                await self._stream_update("error", error_msg)
                return {"type": ResponseType.ERROR.value, "content": error_msg}
                
        except Exception as e:
            logger.error(f"Error in graph execution: {e}")
            await self._stream_update("error", f"Graph execution error: {str(e)}")
            return {"type": ResponseType.ERROR.value, "content": f"Error: {str(e)}"}

    def _extract_plan_from_response(self, response: str) -> list:
        """Extract plan from orchestrator response."""
        try:
            if "[" in response and "]" in response:
                start_bracket = response.split("[")[1]
                json_part = start_bracket.split("]")[0]
                return json.loads("[" + json_part + "]")
        except:
            pass
        return []

    def _extract_final_output(self, result) -> str:
        """Extract the final output from graph execution."""
        # Try to get response_summarizer result first
        if "response_summarizer" in result.results:
            return str(result.results["response_summarizer"].result)
        
        # Fallback to last executed node
        if result.execution_order:
            last_node = result.execution_order[-1]
            return str(last_node.result)
        
        return "No output generated"

    # MCP Client Management Methods (reused from original implementation)
    def _create_mcp_client(self, mcp_config: dict) -> MCPClient:
        """Create an MCP client based on the configuration."""
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
        """Initialize or reinitialize a single MCP client."""
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
        """Process raw server configuration into internal format."""
        transport_type = server_config.get("transportType", "stdio")
        
        return {
            "name": server_config.get("name", mcp_name),
            "is_streamable_http": transport_type == "streamable_http",
            "is_sse": transport_type == "sse", 
            "is_stdio": transport_type not in ["streamable_http", "sse"],
            "mcp_url": server_config.get("url", ""),
            "mcp_command": server_config.get("command", ""),
            "mcp_args": server_config.get("args", []),  # Default to empty list, not empty string
            "headers": server_config.get("headers", {}),
        }

    def _preserve_server_config(self, mcp_name: str, server_config: dict, tool_config: list, is_reconnection: bool = False) -> dict:
        """Preserve all server configuration parameters."""
        if is_reconnection:
            return {**server_config, "tools": tool_config}
        else:
            standard_keys = {
                "name", "agent_type", "usage", "url", "command", "args", 
                "transportType", "rules_prompt", "description", "headers", 
                "disabled", "output_location"
            }
            
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
            
            custom_params = {k: v for k, v in server_config.items() if k not in standard_keys}
            return {**base_config, **custom_params}

    @tool
    def get_all_available_tools(self) -> list:
        """Get all available tools across all connected MCP servers."""
        all_tools = []
        
        for mcp_name, mcp_config in self.mcp_clients.items():
            agent_tools = {
                "agent_name": mcp_config.get("name", mcp_name),
                "agent_type": mcp_config.get("agent_type", "Others"),
                "description": mcp_config.get("description", ""),
                "connected": True,
                "tools": []
            }
            
            tools_config = mcp_config.get("tools", [])
            for tool in tools_config:
                tool_info = {
                    "name": tool.get("name", "Unknown"),
                    "description": tool.get("description", "No description available"),
                    "input_schema": tool.get("inputSchema", {})
                }
                agent_tools["tools"].append(tool_info)
            
            agent_tools["tool_count"] = len(agent_tools["tools"])
            all_tools.append(agent_tools)
        
        all_tools.sort(key=lambda x: x["agent_name"].lower())
        return all_tools

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
            update_data = {
                "type": update_type,
                "content": content,
                "is_partial": is_partial,
            }
            if timestamp:
                update_data["timestamp"] = timestamp
            if metadata:
                update_data["metadata"] = metadata
            if title:
                update_data["title"] = title
            if extra:
                update_data.update(extra)
            await self.stream_callback(update_data)

    # Health check and connection management methods (simplified versions)
    async def _health_check_loop(self):
        """Periodic health check loop for MCP connections."""
        logger.info("Starting health check loop")
        try:
            while self.is_running:
                await asyncio.sleep(self._health_check_interval)
                if not self.is_running:
                    break
                # Simplified health check - just log status
                logger.debug("Health check completed")
        except asyncio.CancelledError:
            logger.info("Health check loop cancelled")

    async def stop(self):
        """Stop the chatbot."""
        self.is_running = False
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
        logger.info("Graph MCP Chatbot stopped")

    async def cleanup(self):
        """Clean up all resources."""
        await self.stop()
        self.mcp_clients.clear()
        logger.info("Graph MCP Chatbot cleanup completed")

    async def continue_with_tool_approval(
        self, 
        agent_name: str, 
        interrupt_ids: list, 
        approval_responses: list, 
        original_query: str = None
    ) -> Dict[str, Any]:
        """Continue agent execution after tool approval."""
        try:
            logger.info(f"Executing approved tools for {agent_name} with {len(interrupt_ids)} approvals")
            
            # Import the approval cache functions
            from .hooks.approval_hooks import set_tool_approval, clear_tool_approval
            
            # Set approvals for all interrupt IDs
            always_approve_tools = []
            for i, (interrupt_id, approval_response) in enumerate(zip(interrupt_ids, approval_responses)):
                # Extract the tool name from the pending tool calls
                tool_name = getattr(self, '_pending_tool_calls', {}).get(interrupt_id, {}).get('tool_name', 'unknown')
                
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
                # Re-execute the graph with approvals cached
                await self._stream_update("thinking", f"Re-executing {agent_name} with approved tools...")
                
                # For graph-based execution, we need to continue from where we left off
                # This is a simplified approach - in a full implementation, you might want to
                # resume the graph execution from the specific node
                result = await self._execute_graph_with_streaming(original_query or self.original_query)
                
                return result
                    
            finally:
                # Clean up all temporary approvals
                for interrupt_id in interrupt_ids:
                    clear_tool_approval(interrupt_id)
                    
        except Exception as e:
            logger.error(f"Error continuing agent execution after approval: {e}")
            await self._stream_update("error", f"Error executing approved tools: {str(e)}")
            return {"type": ResponseType.ERROR.value, "content": f"Error: {str(e)}"}

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

    def update_config(self, new_config: ChatbotConfig):
        """Update the chatbot configuration."""
        self.config = new_config
        self.model = BedrockModel(model_id=self.config.model.primary_model_id)
        self.cheaper_model = BedrockModel(model_id=self.config.model.cheaper_model_id)
        
        if self.response_summarizer:
            self.response_summarizer = ResponseSummarizer(
                model_id=self.config.model.cheaper_model_id)
        
        global logger
        logger = setup_logging(self.config)
        logger.info(f"Configuration updated: {self.config}")