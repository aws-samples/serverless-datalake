from mcp import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client
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
# Configure logging
import sys

def setup_logging(config: ChatbotConfig):
    """Setup logging based on configuration."""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/database_mcp_clients.log")
        ]
    )
    
    # Set specific logger level
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    return logger

# Initialize with default config for now - will be updated when chatbot is created
logger = setup_logging(DEFAULT_CONFIG)

class ResponseType(Enum):
    """Enum for different response types."""
    SUCCESS = "success"
    ERROR = "error"
    CLARIFICATION = "clarification"
    CONFIRMATION_NEEDED = "confirmation_needed"
    SQL_CONFIRMATION_NEEDED = "sql_confirmation_needed"
    TOOL_APPROVAL_NEEDED = "tool_approval_needed"
    PARTIAL = "partial"
    DASHBOARD_FILE = "dashboard_file"
    WIDGET_FILE = "widget_file"
    HTML_CONTENT = "html_content"

@dataclass
class AgentResponse:
    """Standardized agent response."""
    agent_name: str
    response: Any
    success: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class SQLQueryRequest:
    """SQL query request that needs human confirmation."""
    query: str
    database_name: str
    output_location: str
    catalog_name: str = "AwsDataCatalog"
    workgroup: str = "primary"
    limit: Optional[int] = 100
    agent_name: str = ""
    original_query: str = ""
    request_id: str = ""
    
    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())

class SQLQueryInterceptor:
    """Intercepts and manages SQL query confirmations."""
    
    def __init__(self):
        self.pending_queries: Dict[str, SQLQueryRequest] = {}
        self.approved_queries: Dict[str, SQLQueryRequest] = {}
        
    def add_pending_query(self, sql_request: SQLQueryRequest) -> str:
        """Add a SQL query that needs confirmation."""
        self.pending_queries[sql_request.request_id] = sql_request
        return sql_request.request_id
        
    def approve_query(self, request_id: str) -> Optional[SQLQueryRequest]:
        """Approve a pending SQL query."""
        if request_id in self.pending_queries:
            query_request = self.pending_queries.pop(request_id)
            self.approved_queries[request_id] = query_request
            return query_request
        return None
        
    def reject_query(self, request_id: str) -> bool:
        """Reject a pending SQL query."""
        if request_id in self.pending_queries:
            del self.pending_queries[request_id]
            return True
        return False
        
    def get_pending_query(self, request_id: str) -> Optional[SQLQueryRequest]:
        """Get a pending query by ID."""
        return self.pending_queries.get(request_id)
        
    def clear_old_queries(self, max_age_minutes: int = 30):
        """Clear old pending queries to prevent memory leaks."""
        # This would need timestamp tracking in a production system
        pass

import json


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_data)

logger.setLevel(logging.INFO)


# Visualization types for dashboard building
VISUALIZATION_TYPES = {
    "line_chart": "Data that changes over time (sales trends, user growth). Line chart for time-series data",
    "bar_chart": "Comparing categories or groups (sales by region, products by category). Bar chart for comparing categories",
    "pie_chart": "Showing composition or proportion (market share, budget allocation). Pie chart for showing proportions",
    "scatter_plot": "Relationship between two variables (price vs. rating, age vs. salary). Scatter plot for correlation analysis",
    "heatmap": "Showing patterns or intensity across multiple dimensions (activity by hour/day)",
    "table": "Detailed individual records or aggregates requiring precise values",
    "gauge": "KPIs with target values (sales goals, customer satisfaction)",
    "funnel": "Sequential process steps with drop-offs (sales funnel, user journey)",
}


class MCPClientChatbot:
    """
    A persistent chatbot that connects to any database MCP server and stays running
    for continuous database interactions.
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

        # Dashboard-specific agents
        self.schema_analyzer_agent = None
        self.dashboard_designer_agent = None
        self.html_generator_agent = None
        self.conversation_manager = None
        self.session_manager = None
        self.collected_datasets = []
        self.total_datasets=0
        self.response_summarizer = None
        self.html_widget_generator_agent = None
        
        # SQL Query Interceptor for human confirmation
        self.sql_interceptor = SQLQueryInterceptor()

    async def _handle_error(self, error_message: str, context: str = ""):
        """Handle errors consistently with proper logging and user feedback."""
        full_message = f"{context}: {error_message}" if context else error_message
        logger.error(full_message)
        await self._stream_update("error", error_message)
        await self._stream_update("end", timestamp=datetime.now().isoformat())
        
    async def _safe_agent_execution(self, agent_name: str, query: str, 
                                  previous_responses: List[AgentResponse] = None) -> Optional[AgentResponse]:
        """Safely execute an agent with proper error handling."""
        try:
            if previous_responses is None:
                previous_responses = []
                
            response = await self._execute_mcp_agent(agent_name, query, previous_responses)
            return response
        except Exception as e:
            logger.error(f"Error executing agent {agent_name}: {e}")
            return AgentResponse(agent_name, "", False, str(e))
    
    def verifier_agent_builder(self):
        """Verifier agent to check if the query is resolved."""
        try:
            logger.info("Building verifier agent")
            verifier_prompt = f"""
            You are a Verifier agent, designed to check if the query is resolved.
            You will be given the user query, the list of agents that were called, the agent responses, and the final response.
            You will need to check if the query is resolved.
            You will output a JSON object in the following format:
            {{
                "is_sufficient": True or False,
                "needs_clarification": True or False,
                "clarification_message": If needs_clarification is True, you will need to return the clarification message.
            }}
            - MANDATORY: You will only return a json object and nothing else.
            """
            
            if not self.session_manager:
                logger.warning("Session manager not initialized for verifier agent, creating a default one")
                self.session_manager = FileSessionManager(session_id=f"default_verifier_{int(time.time())}")
                
            if not self.conversation_manager:
                logger.warning("Conversation manager not initialized for verifier agent, creating it now")
                self.conversation_manager_builder()
                
            self.verifier_agent = Agent(
                system_prompt=verifier_prompt, 
                model=self.model, 
                name="Verifier_Agent",
                conversation_manager=self.conversation_manager, 
                session_manager=self.session_manager,
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
        orchestrator_prompt = f"""
        You are a Multi-Agent Orchestrator designed to coordinate support across multiple agents.
        
        **Available Agents:**
        {', '.join([f"Agent: {client['name']}, MCP_Agent: yes, Type: {client['agent_type']}, Description: {client['description']} {client['usage']}" for client in self.mcp_clients.values()])}
        - Agent: DashboardBuilder, Description: Specialized agent for building dashboards from collected data
        
        **Your Role:**
        1. As an orchestrator analyze user queries and determine the most appropriate agents to handle them
        2. Create execution plans with ordered agent calls.
        3. Act as verifier when requested to check if queries are resolved
        
        **Critical Decision Rules:**
        - EXHAUST ALL AGENT OPTIONS FIRST before asking for user clarification
        - Progressive exploration: try different agents on subsequent calls
        - User clarification should be LAST RESORT only when:
          a) All relevant agents have been exhausted
          b) Multiple agents failed to provide sufficient information
          c) Query is genuinely ambiguous
          d) Need specific user preferences that no agent can determine
        
        **Systematic Retry Strategy:**
        - First attempt: Try primary relevant agents
        - Second attempt: Try alternative/secondary agents
        - Third attempt: Combine different agents or specialized approaches
        - Final resort: Seek user clarification with specific, targeted questions
        
        **Output Format - MANDATORY JSON Array:**
        [
            {{
                "agent_name": "AgentName",
                "step_number": 1
            }}
        ]
        
        **For User Clarification:**
        [
            {{
                "agent_name": "User",
                "clarification_message": "Specific question after exhausting all agents",
                "step_number": 1
            }}
        ]
        
        **For Verification Role:**
        [
            {{
                "agent_name": "User",
                "can_answer": "yes|no",
                "tool_error": "yes|no",
                "tool_name": "ToolName (optional - only if tool_error is yes)",
                "step_number": 1
            }}
        ]
        
        **Agent Exploration Checklist (before calling User):**
        - [ ] Attempted all database agents that might contain relevant data?
        - [ ] Tried agents with overlapping capabilities?
        - [ ] Considered unconventional but potentially relevant agents?
        - [ ] Attempted combination approaches?
        
        REMEMBER: Be resourceful and thorough. User clarification should demonstrate you've exhausted technical solutions.
        """
        try:
            logger.info("Building orchestrator agent")
            if not self.session_manager:
                logger.warning("Session manager not initialized, creating a default one")
                self.session_manager = FileSessionManager(session_id=f"default_{int(time.time())}")
                
            if not self.conversation_manager:
                logger.warning("Conversation manager not initialized, creating it now")
                self.conversation_manager_builder()
                
            self.orchestrate_agent = Agent(
                system_prompt=orchestrator_prompt, 
                model=self.model,
                conversation_manager=self.conversation_manager, 
                session_manager=self.session_manager,
                agent_id=str(uuid.uuid4())
            )
            logger.info("Orchestrator agent created successfully")
        except Exception as e:
            logger.error(f"Error creating orchestrator agent: {e}")
            # Set to None to ensure we know it failed
            self.orchestrate_agent = None
            raise e

    async def start(self):
        """Start the chatbot and initialize all components."""
        try:
            print("🤖 Starting MCP Chatbot...")
            print("=" * 50)
            logger.info("Starting MCP Chatbot")
            
            # Initialize MCP clients
            for mcp_name, server_config in self.sse_urls.items():
                # Skip disabled servers
                if server_config.get("disabled", False):
                    logger.info(f"Skipping disabled MCP server: {mcp_name}")
                    continue
                    
                mcp_name = server_config["name"] if "name" in server_config else str(mcp_name).capitalize()
                is_streamable_http = False
                is_sse = False
                is_stdio = False
                sse_url = server_config["url"] if "url" in server_config else ""
                mcp_command = server_config["command"] if "command" in server_config else ""
                mcp_args = server_config["args"] if "args" in server_config else ""
                agent_type = server_config["agent_type"] if "agent_type" in server_config else "Others"
                usage = server_config["usage"] if "usage" in server_config else ""
                if "transportType" in server_config and server_config["transportType"]=='sse':
                    is_sse = True
                elif "transportType" in server_config and server_config["transportType"]=='streamable_http':
                    is_streamable_http = True
                else:
                    is_stdio = True
                specialized_agent_mcp_rules = server_config['rules_prompt'] if 'rules_prompt' in server_config else ""
                server_description = server_config["description"] if "description" in server_config else ""
                headers = server_config.get("headers", {})
                try:
                    logger.info(f"Initializing {mcp_name} MCP client at {sse_url}")
                    mcp_client=None
                    if is_sse:
                        # Get headers from server config
                        # if headers:
                        #     logger.info(f"Using custom headers for {mcp_name}: {list(headers.keys())}")
                        #     mcp_client = MCPClient(lambda: sse_client(sse_url, headers=headers))
                        # else:
                        mcp_client = MCPClient(lambda: sse_client(sse_url))
                    
                    elif is_stdio:
                        mcp_client = MCPClient(lambda: stdio_client(
                            StdioServerParameters(
                                command=mcp_command, 
                                args=mcp_args)))
                
                    elif is_streamable_http:
                        # if headers:
                        #     logger.info(f"Using custom headers for {mcp_name}: {list(headers.keys())}")
                        #     mcp_client = MCPClient(lambda: streamablehttp_client(sse_url, headers=headers))
                        # else:
                        mcp_client = MCPClient(lambda: streamablehttp_client(sse_url))
                        
                    with mcp_client:
                        tools = mcp_client.list_tools_sync()
                        # Get Available tools
                        tool_config = []
                        for tool in tools:
                            tool_config.append(
                                {
                                    "name": tool.tool_name,
                                    "description": tool.tool_spec["description"],
                                    "inputSchema": tool.tool_spec["inputSchema"],
                                }
                            )
                        self.mcp_clients[mcp_name] = {
                            "agent_type": agent_type,
                            "name": mcp_name,
                            "description": server_description,
                            "is_streamable_http": is_streamable_http,
                            "is_sse": is_sse,
                            "is_stdio": is_stdio,
                            "mcp_url": sse_url,
                            "mcp_command": mcp_command,
                            "mcp_args": mcp_args,
                            "tools": tool_config,
                            "rules_prompt": specialized_agent_mcp_rules,
                            "usage": usage,
                            "headers": server_config.get("headers", {})
                        }
                    print(f"🛠️ Initialized {mcp_name} MCP client")
                    logger.info(f"Successfully initialized {mcp_name} MCP client with {len(tools)} tools")
                except Exception as e:
                    logger.error(f"Error initializing {mcp_name} MCP client: {e}")
                    print(f"❌ Failed to initialize {mcp_name} MCP client: {e}")
            
            print("✅ MCP Chatbot started successfully")
            print("🎯 Chatbot is ready to process requests via API!")
            print("📊 Dashboard building capabilities enabled!")
            print("=" * 50)
            
            logger.info("MCP Chatbot started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting chatbot: {e}")
            print(f"❌ Failed to start chatbot: {e}")
            raise e
    
    def conversation_manager_builder(self):
        """Build the conversation manager with summarization capabilities."""
        try:
            logger.info("Building conversation manager")
            
            # Create response summarizer utility
            self.response_summarizer = ResponseSummarizer(
                model_id=self.config.model.cheaper_model_id,
                session_id=f"summarizer_{self.session_manager.session_id}"
            )
            logger.info("Created response summarizer utility")
            
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
                
        except Exception as e:
            logger.error(f"Error creating conversation manager: {e}")
            # Set to None to ensure we know it failed
            self.conversation_manager = None
            raise e

    def agent_builder(self, mcp_name, specialized_agent_mcp_rules_prompt, tools, tool_config):
        
        SPECIALIZED_AGENTS_PROMPT = """
        1. You are a specialized agent, designed to answer questions about the following tools:
        {placeholder}
        {agent_special_rules}
        3. Output format will be as follows
        - You will always return a structured jsonlist in the below format only
        {{
            "data": [
                {{ "label": "value", "value": "value" }},
                {{ "label": "value", "value": "value" }},
                {{ "label": "value", "value": "value" }},
                ...
            ]
        }}
        - MANDATORY: You will only return a valid JSON LIST object and nothing else.
        
        Example 1:
        {{
            "data": [
                {{ "device_id": 101, "device_name": "Dispenser 1", "site_id": 1001}},
                {{ "device_id": 102, "device_name": "Dispenser 2", "site_id": 1002 }},
                {{ "device_id": 103, "device_name": "Dispenser 3", "site_id": 1003 }},
                ...
            ]
        }}
        Example 2:
        {{
            "data": [
                {{ "devices_online": 101, "devices_offline": 102, "devices_total": 203 }},
                ...
            ]
        }}
        """

        AGENT_SYSTEM_PROMPT = SPECIALIZED_AGENTS_PROMPT.format(
            placeholder=str(tool_config), agent_special_rules=f"2. Rules: {specialized_agent_mcp_rules_prompt}"
        )
        
        # Create approval hook for this agent
        approval_hook = MCPToolApprovalHook(
            app_name=f"{mcp_name}_agent",
            tools_requiring_approval=None,  # Will use default list
            auto_approve_patterns=None      # Will use default patterns
        )
        
        # Use model from config for non-Athena agents
        agent = Agent(
                name=mcp_name,
                tools=tools,
                model=self.model,
                system_prompt=AGENT_SYSTEM_PROMPT,
                conversation_manager=self.conversation_manager, 
                session_manager=self.session_manager,
                hooks=[approval_hook],  # Add the approval hook
                agent_id=str(uuid.uuid4())
            )
        return agent
    
    def extract_and_fix_json(self, text: str) -> Optional[Dict]:
        """Extract and fix JSON from text with better error handling."""
        try:
            # Find the first '{' and the last '}'
            start_index = text.find('{')
            end_index = text.rfind('}') + 1
            
            if start_index == -1 or end_index == 0:
                logger.warning("No JSON object found in text")
                return None
            
            # Extract the JSON string
            json_str = text[start_index:end_index]
            logger.debug(f"Extracted JSON string of length {len(json_str)}")
            
            # Try to parse directly first
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.info("Direct JSON parsing failed, attempting fixes")
            
            # Apply fixes for common JSON issues
            fixed_json = self._apply_json_fixes(json_str)
            
            try:
                return json.loads(fixed_json)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed even after fixes: {e}")
                logger.debug(f"Problematic JSON: {fixed_json[:200]}...")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error in JSON extraction: {e}")
            return None
    
    def _apply_json_fixes(self, json_str: str) -> str:
        """Apply common JSON fixes."""
        # Remove control characters
        cleaned = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')
        
        # Fix trailing commas
        lines = cleaned.split('\n')
        for i in range(len(lines)):
            if i < len(lines) - 1 and (']' in lines[i+1] or '}' in lines[i+1]):
                lines[i] = lines[i].rstrip(',')
        
        return '\n'.join(lines)
        

    # Function to extract JSON objects from text
    def extract_and_merge_json(self, text):
        # Find all JSON objects in the text
        json_pattern = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}')
        json_matches = json_pattern.findall(text)
        
        # Parse each JSON object
        parsed_jsons = []
        for json_str in json_matches:
            try:
                parsed_json = json.loads(json_str)
                parsed_jsons.append(parsed_json)
            except json.JSONDecodeError:
                print(f"Failed to parse JSON: {json_str[:50]}...")
        
        # Merge JSONs with the same keys
        merged_json = {}
        for parsed_json in parsed_jsons:
            for key, value in parsed_json.items():
                if key in merged_json and isinstance(value, list) and isinstance(merged_json[key], list):
                    # If both are lists, extend the existing list
                    merged_json[key].extend(value)
                else:
                    # Otherwise, just set or overwrite the value
                    merged_json[key] = value
        
        return merged_json
        
    
    def get_json_key(self, input_str_or_json, key):
        try:
            if isinstance(input_str_or_json, dict):
                return input_str_or_json.get(key)  # Use .get() instead of [] to avoid KeyError
            elif isinstance(input_str_or_json, str):
                # Try to parse as JSON first
                try:
                    json_obj = json.loads(input_str_or_json)
                    return json_obj.get(key)
                except json.JSONDecodeError:
                    # Fall back to string parsing only if the key exists in the string
                    if key in input_str_or_json:
                        logger.info(f"Attempting to extract key '{key}' from string using split method")
                        try:
                            return input_str_or_json.split(f"{key}")[1].split(":")[1].split(",")[0].replace('"', '').strip()
                        except (IndexError, AttributeError):
                            logger.warning(f"Failed to extract key '{key}' using string parsing")
                            return None
                    else:
                        logger.debug(f"Key '{key}' not found in string")
                        return None
            else:
                logger.warning(f"Unable to extract key '{key}' from {type(input_str_or_json)}")
                return None
        except Exception as e:
            logger.error(f"Error extracting key '{key}' from input: {e}")
            logger.debug(f"Input data: {input_str_or_json[:200]}..." if isinstance(input_str_or_json, str) else str(input_str_or_json))
            return None
        

    def build_dashboard_agents(self):
        """Build the specialized dashboard agents."""
        try:
            logger.info("Building dashboard agents")
            
            # Check if required components are initialized
            if not self.session_manager:
                logger.warning("Session manager not initialized for dashboard agents, creating a default one")
                self.session_manager = FileSessionManager(session_id=f"default_dashboard_{int(time.time())}")
                
            if not self.conversation_manager:
                logger.warning("Conversation manager not initialized for dashboard agents, creating it now")
                self.conversation_manager_builder()

            # Schema Analyzer Agent (now focuses on visualization suggestions)
            logger.info("Creating schema analyzer agent")
            schema_analyzer_prompt = dedent(
                f"""
            You are an expert data analyst and visualization specialist. Your role is to:
            
            1. **Analyze Collected Data**: Examine data that has been collected from database sources
            2. **Identify Patterns**: Find meaningful patterns, trends, and insights in the data
            3. **Suggest Visualizations**: Recommend appropriate chart types based on data characteristics.
            4. **Consider User Intent**: Match visualizations to the user's query and goals
            
            **Available Visualization Types:**
            {json.dumps(VISUALIZATION_TYPES, indent=2)}
            
            **Output Format:**
            Return a JSON object with the following structure:
            {{
                "suggested_visualizations": [
                    {{
                        "dataset_index": 0,
                        "visualization_type": "chart_type_from_list_above",
                        "rationale": "Why this chart type is appropriate for this data",
                        "data_requirements": "What data format is needed",
                        "user_preference_hint": "Ask user about this visualization preference",
                        "insights": "What insights this visualization could reveal"
                    }}
                ],
                "questions_for_user": [
                    "What specific aspect would you like to focus on?",
                    "Do you prefer trend analysis or comparison views?",
                    "Are you interested in patterns over time or current snapshots?"
                ],
                "data_summary": "Brief summary of what the data shows"
            }}
            
            **Process:**
            1. Analyze the structure and content of collected datasets
            2. Identify the most meaningful ways to visualize each dataset
            3. Consider data volume, types, and relationships
            4. Suggest visualizations that will provide the most insight
            5. Return only valid JSON - no additional text or explanations
            """
            )

            self.schema_analyzer_agent = Agent(
                system_prompt=schema_analyzer_prompt, 
                model=self.model,
                conversation_manager=self.conversation_manager, 
                session_manager=self.session_manager,
                agent_id=str(uuid.uuid4())
            )
            logger.info("Schema analyzer agent created successfully")
            
            # Dashboard Designer Agent (now focuses on data processing and validation)
            logger.info("Creating dashboard designer agent")
            dashboard_designer_prompt = dedent(
                """
            You are a senior data analyst and dashboard designer. Your role is to:
            
            1. **Process Collected Data**: Transform raw data into appropriate formats for visualization
            2. **Validate Data Quality**: Ensure data is clean, complete, and suitable for visualization. Fix bad or incorrect json in the data
            3. **Prepare Visualization Data**: Structure data according to chart requirements
            4. **Handle Edge Cases**: Manage empty data, outliers, and data type mismatches
            
            **Output Format:**
            Return a JSON object with the following structure:
            {{
                "processed_datasets": [
                    {{
                        "dataset_index": 0,
                        "visualization_type": "chart_type",
                        "data": [
                            {{ "label": "value", "value": "value" }},
                            ...
                        ],
                        "summary": "Brief summary of the processed data",
                        "data_quality": "Assessment of data quality",
                        "recommendations": "Any recommendations for visualization"
                    }}
                ],
                "dashboard_title": "Dashboard Title",
                "dashboard_description": "Brief description of the dashboard",
                "data_insights": "Key insights from the data analysis"
            }}
            
            **Process:**
            1. Examine each collected dataset for structure and content
            2. Transform data into the format required by the suggested visualization
            3. Validate data quality and handle any issues
            4. Provide insights and recommendations for each dataset
            5. Return only valid JSON - no additional text
            """
            )

            self.dashboard_designer_agent = Agent(
                system_prompt=dashboard_designer_prompt, 
                model=self.model,
                conversation_manager=self.conversation_manager, 
                session_manager=self.session_manager,
                agent_id=str(uuid.uuid4())
            )
            logger.info("Dashboard designer agent created successfully")



            # HTML Generator Agent - MVP 1 focused on pie charts and tables
            logger.info("Creating HTML generator agent")
            html_generator_prompt = dedent(
                """
            You are a frontend engineer creating MVP 1 dashboards. Your role is to:
            
            1. **Generate Simple HTML Dashboard**: Create a basic, functional HTML dashboard
            2. **Basic Styling**: Use Tailwind CSS for clean, simple design
            
            **MVP 1 Requirements:**
            - Use Chart.js (via CDN) ONLY for pie charts
            - Use HTML tables for detailed data
            - Use Tailwind CSS (via CDN) for basic styling
            - Simple card layout - one chart/table per card
            - Minimal, clean design
            
            **Output Format:**
            Return only a complete, valid HTML document. Include:
            - HTML5 structure with Chart.js and Tailwind CSS CDN
            - Pie charts for categorical data
            - HTML tables for detailed data
            - Simple card layout
            
            **Important:**
            - Return only HTML - no explanations
            """
            )

            self.html_generator_agent = Agent(
                system_prompt=html_generator_prompt, 
                model=self.model,
                conversation_manager=self.conversation_manager, 
                session_manager=self.session_manager,
                agent_id=str(uuid.uuid4())
            )
            logger.info("HTML generator agent created successfully")
            
            html_widget_generator_prompt = dedent(
                """
            You are a frontend engineer creating widgets. Your role is to:
            
            1. **Generate Simple HTML Widget**: Create a basic, functional HTML Widget
            2. **Basic Styling**: Use Tailwind CSS for clean, simple design
            
            **MVP 1 Requirements:**
            - Use Chart.js or D3.js (via CDN) as a charting library
            - Use HTML tables for detailed data
            - Use Tailwind CSS (via CDN) for basic styling
            - Simple card layout - one chart/table per card
            - Minimal, clean design
            
            **Output Format:**
            Return only a complete, valid HTML document. Include:
            - HTML5 structure with Chart.js and Tailwind CSS CDN
            - Pie charts for categorical data
            - HTML tables for detailed data
            - Simple card layout
            
            **Important:**
            - MANDATORY: Return only HTML - no explanations
            - MANDATORY: You will only create a single widget at a time.
            - MANDATORY: Focus on functionality over fancy features
            """
            )

            self.html_widget_generator_agent= Agent(
                system_prompt=html_widget_generator_prompt, 
                model=self.model,
                conversation_manager=self.conversation_manager, 
                session_manager=self.session_manager,
                agent_id=str(uuid.uuid4())
            )

        except Exception as e:
            logger.error(f"Error building dashboard agents: {e}")
            # Set to None to ensure we know they failed
            self.schema_analyzer_agent = None
            self.dashboard_designer_agent = None
            self.html_generator_agent = None
            raise e

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

    async def build_dashboard(
        self, user_query: str, stream_callback=None
    ) -> Dict[str, Any]:
        """
        Build a complete dashboard based on the user query.
        First collects data from database MCP servers, then asks for visualization preferences.

        Args:
            user_query: The user's dashboard request
            stream_callback: Optional callback for streaming progress updates

        Returns:
            Dictionary containing the dashboard HTML and metadata
        """
        try:
            # Step 1: Collect data from database MCP servers
            if stream_callback:
                await self._stream_update(
                    "thinking",
                    "🔍 Collecting data from your databases to understand what's available...",
                )

            # Collect data from all available MCP servers
            collected_data = await self._collect_data_from_mcp_servers(
                user_query, stream_callback
            )

            if not collected_data or not collected_data.get("datasets"):
                if stream_callback:
                    await self._stream_update(
                        "error",
                        "No data found in the databases. Please check your data sources or try a different query.",
                    )
                return {
                    "type": "error",
                    "content": "No data available for dashboard generation",
                }
            else:
                await self._stream_update(
                    "thinking",
                    f"✅ Data collected successfully! {collected_data}",
                    is_partial=True,
                )
            # Step 2: Ask for visualization preferences
            if stream_callback:
                await self._stream_update(
                    "thinking",
                    "📊 Analyzing the collected data and suggesting visualization options...",
                )

            adapted_visualizations = await self._adapt_visualizations_to_data(
                collected_data, stream_callback
            )

            # Step 4: Generate HTML dashboard
            if stream_callback:
                await self._stream_update(
                    "thinking",
                    "🎨 Generating interactive dashboard with optimized charts...",
                )

            html_response = await self._generate_dashboard_html(
                adapted_visualizations, user_query
            )

            if stream_callback:
                await self._stream_update(
                    "content",
                    "✅ Dashboard generated successfully! Here's your interactive dashboard:",
                    is_partial=False,
                )

            # Return the complete dashboard
            return {
                "type": "dashboard",
                "html": html_response,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "user_query": user_query,
                    "data_summary": collected_data.get("summary", ""),
                    "visualization_adaptations": adapted_visualizations.get(
                        "adaptations", []
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error building dashboard: {e}")
            if stream_callback:
                await self._stream_update("error", f"Failed to build dashboard: {str(e)}")
            return {
                "type": "error",
                "content": f"Dashboard generation failed: {str(e)}",
            }

    async def _ask_visualization_preferences(
        self, suggestions: Dict[str, Any], stream_callback
    ) -> Dict[str, Any]:
        """
        Ask user for visualization preferences when multiple options are available.

        Args:
            suggestions: Visualization suggestions from the analyzer
            stream_callback: Callback for streaming updates

        Returns:
            Dictionary containing user preferences or default choices
        """
        questions = suggestions.get("questions_for_user", [])
        suggested_viz = suggestions.get("suggested_visualizations", [])

        if not questions or len(suggested_viz) <= 1:
            # No need to ask questions if there's only one suggestion
            return suggestions

        # For now, we'll use the first suggestion as default
        # In a full implementation, this could be an interactive prompt
        if stream_callback:
            await self._stream_update(
                "thinking",
                f"📊 I found {len(suggested_viz)} potential visualizations. Using the most appropriate ones based on your data...",
                timestamp=datetime.now().isoformat(),
            )

        # Return the suggestions with a note about the choice
        return {
            **suggestions,
            "user_choice_note": "Selected most appropriate visualizations based on data characteristics",
        }

    
    async def _adapt_visualizations_to_data(
        self, collected_data: dict, stream_callback=None
    ) -> dict:
        """
        MVP 1: Default to pie charts for categorical data, tables for detailed data.
        """
        visualizations = []
        for idx, dataset in enumerate(collected_data.get("datasets", [])):
            # Simple logic: if data looks like key-value pairs, use pie chart, otherwise table
            try:
                parsed_data = (
                    json.loads(dataset) if isinstance(dataset, str) else dataset
                )
                data_items = parsed_data.get("data", [])

                # Check if data is suitable for pie chart (has 2-10 items with numeric values)
                if (
                    isinstance(data_items, list)
                    and 2 <= len(data_items) <= 10
                    and all(
                        isinstance(item, dict) and len(item) == 2 for item in data_items
                    )
                ):
                    viz_type = "pie_chart"
                    reason = (
                        "Categorical data with numeric values - suitable for pie chart"
                    )
                else:
                    viz_type = "table"
                    reason = "Detailed data - best displayed as table"
            except:
                viz_type = "table"
                reason = "Default to table for data parsing issues"

            visualizations.append(
                {
                    "dataset_index": idx,
                    "visualization_type": viz_type,
                    "data": dataset,
                    "adaptation_reason": reason,
                }
            )
        return {
            "final_visualizations": visualizations,
            "adaptations": [
                f"MVP 1: Using pie charts and tables based on data characteristics"
            ],
        }

    def _analyze_data_characteristics(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the characteristics of a dataset to determine appropriate visualization.

        Args:
            dataset: Dataset to analyze

        Returns:
            Dictionary containing data characteristics
        """
        characteristics = []

        if dataset.get("type") == "table":
            headers = dataset.get("headers", [])
            rows = dataset.get("rows", [])

            # Count data points
            num_rows = len(rows)
            num_columns = len(headers)

            if num_rows == 0:
                characteristics.append("no_data")
            elif num_rows == 1:
                characteristics.append("single_data_point")
            elif num_rows < 5:
                characteristics.append("few_data_points")
            elif num_rows > 100:
                characteristics.append("many_data_points")

            # Check for time-based data
            time_indicators = ["date", "time", "year", "month", "day", "timestamp"]
            has_time_data = any(
                indicator in str(headers).lower() for indicator in time_indicators
            )
            if has_time_data:
                characteristics.append("time_series")

            # Check for categorical vs numerical data
            if num_columns >= 2:
                # Simple heuristic: if first column looks like categories and second like numbers
                try:
                    first_col_values = [row[0] for row in rows if len(row) > 0]
                    second_col_values = [row[1] for row in rows if len(row) > 1]

                    # Check if second column contains numbers
                    numeric_count = sum(
                        1
                        for val in second_col_values
                        if str(val).replace(".", "").replace("-", "").isdigit()
                    )
                    if numeric_count > len(second_col_values) * 0.8:  # 80% numeric
                        characteristics.append("categorical_numerical")
                except:
                    pass

        elif dataset.get("type") == "text":
            characteristics.append("text_data")

        return {
            "characteristics": characteristics,
            "dataset_type": dataset.get("type"),
            "source": dataset.get("source"),
        }

    def _adapt_chart_type(
        self, original_type: str, data_analysis: Dict[str, Any]
    ) -> str:
        """
        Adapt chart type based on data characteristics.

        Args:
            original_type: Originally suggested chart type
            data_analysis: Analysis of data characteristics

        Returns:
            Adapted chart type
        """
        characteristics = data_analysis.get("characteristics", [])

        # Adaptation rules
        if "no_data" in characteristics:
            return "table"  # Show empty state clearly

        if "single_data_point" in characteristics:
            return "gauge"  # Single value is better as gauge

        if "few_data_points" in characteristics:
            if original_type in ["line_chart", "area_chart"]:
                return "bar_chart"  # Few points better as bars
            elif original_type == "scatter_plot":
                return "table"  # Too few points for scatter

        if "many_data_points" in characteristics:
            if original_type == "pie_chart":
                return "bar_chart"  # Too many slices for pie
            elif original_type == "table":
                return "bar_chart"  # Better visualization for many points

        if "time_series" in characteristics:
            if original_type not in ["line_chart", "area_chart", "bar_chart"]:
                return "line_chart"  # Time data should be line chart

        if "categorical_numerical" in characteristics:
            if original_type in ["line_chart", "area_chart"]:
                return "bar_chart"  # Categories better as bars

        if "text_data" in characteristics:
            return "table"  # Text data as table

        return original_type

    def _apply_adaptations(
        self, suggestions: Dict[str, Any], adaptations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply adaptations to the original suggestions.

        Args:
            suggestions: Original visualization suggestions
            adaptations: List of adaptations to apply

        Returns:
            List of final visualizations with adaptations applied
        """
        final_visualizations = []

        for suggestion in suggestions.get("suggested_visualizations", []):
            dataset_index = suggestion.get("dataset_index", 0)

            # Find matching adaptation
            adaptation = next(
                (a for a in adaptations if a.get("dataset_index") == dataset_index),
                None,
            )

            final_viz = suggestion.copy()
            if adaptation:
                final_viz["visualization_type"] = adaptation["adapted_type"]
                final_viz["adaptation_reason"] = adaptation["reason"]

            final_visualizations.append(final_viz)

        return final_visualizations

    async def _generate_dashboard_html(
        self, visualizations: Dict[str, Any], user_query: str, is_single_widget=False
    ) -> str:
        """
        Generate HTML dashboard with the adapted visualizations and save to file.
        

        Args:
            visualizations: Final visualizations with adaptations
            user_query: Original user query

        Returns:
            HTML string for the dashboard
        """
        dashboard_features = ""
        if not is_single_widget:
            dashboard_features = "- Add a fixed navigation header with AWS logo.\n         - Implement a dark mode toggle\n         - Create card-based components with subtle shadows and hover effects\n         - Use rounded corners (border-radius: 12px) for containers"
        
        html_prompt = f"""
        I need to create a professional, interactive HTML {"widget" if is_single_widget else "dashboard"} based on the user's query and visualization requirements.
        {"Mandatory- You will always generate a single widget. If there are multiple datasets try combining them into a single widget else ignore other datasets" if is_single_widget else ""}
        ## User Query
        {user_query}
        ## Visualization Specifications
        {json.dumps(visualizations, indent=2)}
        ## Requirements

        ### Core Functionality
        - Create a complete, standalone HTML file with all necessary components embedded
        - Make the {"widget" if is_single_widget else "dashboard"} fully responsive across desktop, tablet, and mobile devices
        - Implement proper data visualization based on the specifications.{" And only generate one visualization" if is_single_widget else ""}
        - Ensure all chart elements are properly labeled and accessible.{" And only generate one chart" if is_single_widget else ""}
        {dashboard_features}
        - Below the title write a one-line summary of the generated {"widget" if is_single_widget else "dashboard"}
        - MANDATORY: Use standard HTML syntax with proper quotes (") for attributes, not escaped quotes (\") which would break HTML parsing
        
        ### Visualization Features
        - Use Chart.js or D3.js for creating interactive visualizations
        - For each visualization, implement:
           - Tooltips showing detailed information on hover
           - Legends that can be toggled on/off
        
        ### Design and Layout
        - Use Tailwind CSS for responsive styling and layout
        - Implement a clean, modern UI with appropriate spacing and typography
        - Use Inter or Poppins as the primary font
        - Implement a clear typography hierarchy:
        * Headings: 2.5rem/2rem/1.5rem
        * Body: 1rem
        * Caption: 0.875rem
        - Add export functionality for charts and tables (e.g., PNG, CSV)
        - Use a cohesive color palette that ensures good contrast and readability
        - Include a header with the {"widget" if is_single_widget else "dashboard"} title based on the user query
        - {"Just a title, subtitle and one chart only for this widget" if is_single_widget else "Organize visualizations in a logical grid layout with appropriate sizing"}
        
        ### Additional Features
        {"" if is_single_widget else "- MANDATORY: - Add Export options (PDF, PNG, CSV). Filter and search capabilities for tables"}
        - MANDATORY: Include a timestamp showing when the {"widget" if is_single_widget else "dashboard"} was generated.
        7. Accessibility:
        - High contrast options
        - ARIA labels
        - Keyboard navigation
        - Screen reader compatibility
        8. Animations:
        - Subtle micro-interactions
        - Chart loading animations
        - Smooth page transitions
        - Hover state animations
        ## Output Format
        Provide a complete HTML document with all necessary scripts, styles, and content embedded to ensure it works as a standalone file.
        
        ## Example Structure
        ```html
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <!-- Meta tags, title, and embedded stylesheets -->
        </head>
        <body>
            <!-- {"Widget" if is_single_widget else "Dashboard"} header -->
            <!-- {"Widget Subtitle" if is_single_widget else ""} --> 
            <!-- Chart containers with dropdown selectors -->
            <!-- {"" if is_single_widget else "Download"}  button -->
            <!-- Embedded scripts for Chart.js and interactivity -->
        </body>
        </html>
        """
        response=None
        if is_single_widget:
            response = self.html_widget_generator_agent(html_prompt)
        else:    
            response = self.html_generator_agent(html_prompt)
        html_content = str(response)
       
        file_name = "dashboard"
        # Use pathlib for relative path
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent.parent
        dashboard_dir = project_root / self.config.dashboard.output_directory
        
        if is_single_widget:
            file_name = "widget"
            # Use pathlib for relative path
            current_file = pathlib.Path(__file__)
            project_root = current_file.parent.parent.parent
            dashboard_dir = project_root / "generated_widgets"
            
        # extract title from html content
        if '<title>' in html_content and '</title>' in html_content:
            file_name = html_content.split('<title>')[1].split('</title>')[0]
        # Create the directory if it doesn't exist        
        dashboard_dir.mkdir(exist_ok=True, parents=True)
        # Generate a unique filename based on timestamp and query
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{file_name}_{timestamp}.html"
        # Save the dashboard HTML to file
        filepath = dashboard_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return filename, html_content

    def get_mcp_client(self, mcp_name):
        """Get the MCP client."""
        mcp_client = None
        if mcp_name in self.mcp_clients:
            mcp_config = self.mcp_clients[mcp_name]
            if mcp_config["is_sse"]:
                # Get headers from server config
                headers = mcp_config.get("headers", {})
                if headers:
                    logger.info(f"Using custom headers for {mcp_name}: {list(headers.keys())}")
                    mcp_client = MCPClient(
                        lambda: sse_client(self.mcp_clients[mcp_name]["mcp_url"], headers=headers)
                    )
                else:
                    mcp_client = MCPClient(
                        lambda: sse_client(self.mcp_clients[mcp_name]["mcp_url"])
                    )
            elif mcp_config["is_stdio"]:
                mcp_client = MCPClient(lambda: stdio_client(
                    StdioServerParameters(
                        command=mcp_config["mcp_command"], 
                        args=mcp_config["mcp_args"])))
            elif mcp_config["is_streamable_http"]:
                mcp_client = MCPClient(lambda: streamablehttp_client(mcp_config['mcp_url']))
                    
        return mcp_client
    
    def create_all_agents(self, user_id="Sample", session_id=None):
        """Create all agents needed for the chatbot."""
        try:
            logger.info(f"Creating all agents for user {user_id}, session {session_id}")
            
            # Create session manager
            if not session_id:
                session_id = f"session_{int(time.time())}"
            self.session_manager = FileSessionManager(session_id=f"{user_id}_{session_id}")
            logger.info(f"Session manager created with ID: {user_id}_{session_id}")
            
            # Create conversation manager
            self.conversation_manager_builder()
            logger.info("Conversation manager created")
            
            # Create orchestrator agent
            self.orchestrate_agent_builder()
            logger.info("Orchestrator agent created")
            
            # Create verifier agent
            self.verifier_agent_builder()
            logger.info("Verifier agent created")
            
            # Create dashboard agents
            self.build_dashboard_agents()
            logger.info("Dashboard agents created")

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
        self.schema_analyzer_agent = None
        self.dashboard_designer_agent = None
        self.html_generator_agent = None
        self.html_widget_generator_agent = None
        
        # Clean up response summarizer
        if self.response_summarizer:
            self.response_summarizer.cleanup()
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
            self.response_summarizer.cleanup()
            self.response_summarizer = ResponseSummarizer(
                model_id=self.config.model.cheaper_model_id,
                session_id=f"summarizer_{self.session_manager.session_id if self.session_manager else int(time.time())}"
            )
        
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

    async def _collect_data_from_mcp_servers(self, user_query: str, stream_callback=None) -> Dict[str, Any]:
        """Collect data from all available MCP servers with dataset limit."""
        collected_datasets = []
        
        # Limit datasets based on configuration
        max_datasets = self.config.dashboard.max_datasets
        
        for agent_name in list(self.mcp_clients.keys())[:max_datasets]:
            try:
                response = await self._safe_execute_agent(agent_name, user_query, [])
                if response and response.success:
                    json_resp = self.extract_and_fix_json(response.response)
                    if json_resp:
                        collected_datasets.append(str(json_resp))
                        self.collected_datasets.append(str(json_resp))
                        self.total_datasets += 1
                        
                        # Stop if we've reached the max datasets
                        if len(collected_datasets) >= max_datasets:
                            break
            except Exception as e:
                logger.error(f"Error collecting data from {agent_name}: {e}")
                continue
        
        return {
            "datasets": collected_datasets,
            "summary": f"Collected {len(collected_datasets)} datasets from {len(self.mcp_clients)} available sources"
        }

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
        
    async def _get_orchestrator_response(self, user_query):
        """Get and validate orchestrator response."""
        if not self.orchestrate_agent:
            # Try to recreate the agent if it's not available
            try:
                logger.info("Orchestrator agent not found, attempting to create it")
                self.create_all_agents(user_id="system", session_id=f"session_{int(time.time())}")
                if not self.orchestrate_agent:
                    await self._handle_error("Orchestrator agent not available. Please restart the system.")
                    return None
            except Exception as e:
                await self._handle_error(f"Failed to create orchestrator agent: {str(e)}")
                return None
            
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
            
    async def create_dashboard(self, user_query: str, is_single_widget=False) -> Dict[str, Any]:
        """Complete dashboard creation process from user query to final HTML."""
        try:
            # Step 1: Collect data from database MCP servers
            await self._stream_update(
                "thinking",
                f"🔍 Collected data from {self.total_datasets}",
                is_partial=True
            )
            
            if len(self.collected_datasets) <= 0:
                await self._stream_update(
                    "error",
                    "No data found in the databases. Please check your data sources or try a different query."
                )
                return {
                    "type": "error",
                    "content": "No data available for dashboard generation"
                }
            
            # Step 2: Analyze data and suggest visualizations
            await self._stream_update(
                "thinking",
                "📊 Analyzing data and suggesting visualizations...",
                is_partial=True
            )
            
            # Use schema analyzer agent to suggest visualizations
            analyzer_prompt = f"""Analyze this collected data and suggest appropriate visualizations:\n{self.collected_datasets}"""
            visualization_suggestions = self.schema_analyzer_agent(analyzer_prompt)
            
            # Step 3: Process and adapt visualizations to data
            await self._stream_update(
                "thinking",
                "🎨 Adapting visualizations to your data...",
                is_partial=True
            )
            
            # Use dashboard designer agent to process data
            designer_prompt = f"""Process this data for visualization:\n{self.collected_datasets}\n\nWith these visualization suggestions:\n{visualization_suggestions}"""
            processed_data = self.dashboard_designer_agent(designer_prompt)
            
            # Step 4: Generate HTML dashboard
            await self._stream_update(
                "thinking",
                "🖥️ Generating interactive dashboard...",
                is_partial=True
            )
            
            # Generate final HTML
            file_name, html_content = await self._generate_dashboard_html(
                {"final_visualizations": json.loads(str(processed_data)).get("processed_datasets", [])},
                user_query, is_single_widget
            )
            
            widget_or_dashboard = "Widget" if is_single_widget else "Dashboard"
            await self._stream_update(
                "content",
                f"✅ {widget_or_dashboard} generated successfully!",
                is_partial=False
            )
            
            # Return the complete dashboard
            await self._stream_update(
                update_type="dashboard_file",
                content=file_name,
                is_partial=False,
                timestamp=datetime.now().isoformat(),
                metadata= {
                    "generated_at": datetime.now().isoformat(),
                    "user_query": user_query,
                    "data_summary": ','.join(self.collected_datasets)}
            )
            return {
                "type": {"widget_file" if is_single_widget else "dashboard_file"},
                "file_name": file_name,
                "message": f"{widget_or_dashboard} generated successfully!",
            }
            
        except Exception as e:
            logger.error(f"Error creating dashboard: {e}")
            await self._stream_update("error", f"Failed to create dashboard: {str(e)}")
            return {
                "type": "error",
                "content": f"Dashboard generation failed: {str(e)}"
            }

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
        agent_name = agent_config["agent_name"]
        step_number = agent_config.get("step_number", 1)
        
        logger.info(f"Executing step {step_number}: {agent_name}")
        
        # Handle user clarification requests
        if agent_name.lower() == 'user':
            clarification_msg = agent_config.get('clarification_message', 'Clarification needed')
            await self._stream_update('thinking', clarification_msg)
            agent_responses.append({"agent_name": agent_name, "response": clarification_msg})
            return {
                "status": "clarification_needed",
                "responses": agent_responses
            }
        
        # Execute DashboardBuilder
        if agent_name == 'DashboardBuilder':
            await self._stream_update('thinking', 'Generating Dashboard...')
            dashboard_response = await self.create_dashboard(original_query, is_single_widget)
            if dashboard_response['type'] == 'error':
                return {
                    "status": "error",
                    "error_response": dashboard_response
                }
            agent_responses.append({"agent_name": agent_name, "response": dashboard_response})
            return {
                "status": "success",
                "responses": agent_responses
            }
        
        # Execute MCP agents
        elif agent_name in self.mcp_clients:
            enhanced_query = self._build_enhanced_query(original_query, agent_responses)
            response = await self._safe_execute_agent(agent_name, enhanced_query, agent_responses)
            
            if response and response.success:
                json_resp = self.extract_and_fix_json(response.response)
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

    async def continue_with_tool_approval(self, agent_name: str, query: str, interrupt_id: str, 
                                        approval_response: str, pending_responses: List = None,
                                        remaining_plan: List = None, original_query: str = None) -> Optional[str]:
        """Continue agent execution after tool approval and resume the orchestrated plan."""
        try:
            logger.info(f"Executing approved tool for {agent_name} with approval: {approval_response}")
            
            # Check if the user denied the request
            if approval_response.lower() in ['deny', 'n', 'no']:
                await self._stream_update("content", f"Tool execution denied by user for {agent_name}")
                # If denied, we should still continue with the remaining plan
                # if remaining_plan and len(remaining_plan) > 0:
                    #logger.info("Tool denied, but continuing with remaining plan")
                    # return await self._execute_remaining_plan(remaining_plan, original_query or query, pending_responses or [])
                return "Tool execution denied by user"
            
            # Import the approval cache functions
            from .hooks.approval_hooks import set_tool_approval, clear_tool_approval
            
            # Extract the tool name from the pending tool calls
            tool_name = self._pending_tool_calls.get(interrupt_id, {}).get('tool_name', 'unknown')
            
            # Set the approval for this specific tool
            set_tool_approval(interrupt_id, tool_name, approval_response)
            
            # If user chose "always", also set the specific tool for always approve
            if approval_response.lower() in ["always", "a"]:
                if tool_name != 'unknown':
                    self.set_tool_always_approve(tool_name)
                    logger.info(f"Tool {tool_name} added to always approve list")
            
            try:
                # Re-execute the agent with the approval cached
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
                    f"Tool approval required for {result['agent_name']}",
                    extra=result)

                    return result
                elif result:
                    # Add this agent's response to the collection
                    json_resp = self.extract_and_fix_json(result) if isinstance(result, str) else result
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
                # Clean up the temporary approval
                clear_tool_approval(interrupt_id)
                    
        except Exception as e:
            logger.error(f"Error continuing agent execution after approval: {e}")
            await self._stream_update("error", f"Error executing approved tool: {str(e)}")
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
                # Stream the approval request to the UI
                await self._stream_update(
                    "tool_approval_needed",
                    f"Tool approval required for {agent_name}",
                    extra={
                        "interrupt_id": response["interrupt_id"],
                        "reason": response["reason"],
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
        if len(agent_responses) > 0:
            context = "\n".join([
                f"**{resp['agent_name']} Response:**\n{resp['response']}"
                for resp in agent_responses
            ])
            return f"""
            You are an agent in a multi-agent system with specific tools and capabilities.
            1. **PREVIOUS CONTEXT**: Consider these responses from previous agents: {context}.
            2. **PRIMARY RESPONSIBILITY**: Try to answer any part of the question not answered by the previous agents using YOUR available tools.                                                
            3. **TOOL EXPLORATION MANDATE**: 
               - **ALWAYS attempt to use your available tools first** before determining you cannot help
               - Your tools may contain relevant data even if not immediately obvious from the question
               - **Think creatively** about how your tools might provide relevant information
               - **Explore database schemas** using list tools to understand what data is available
               - **Query systematically** to find relevant information that might answer the user's question
            4. **DECISION PROCESS** - Follow this order:
               a) **EXPLORE**: Use listing/discovery tools to understand what data you have access to
               b) **INVESTIGATE**: Query relevant data sources that might contain the requested information  
               c) **ANALYZE**: Examine the data to see if it answers any part of the user's question
               d) **RESPOND**: Only after genuine exploration, determine if you can provide partial or complete answers
            **Original User Query**: {user_query}"""
        else:
            return f"""You are an agent in a multi-agent system with specific tools and capabilities.
            1. **PRIMARY RESPONSIBILITY**: Try to answer any part of the question using YOUR available tools.                                                
            2. **TOOL EXPLORATION MANDATE**: 
               - **ALWAYS attempt to use your available tools first** before determining you cannot help
               - Your tools may contain relevant data even if not immediately obvious from the question
               - **Think creatively** about how your tools might provide relevant information
               - **Explore database schemas** using list tools to understand what data is available
               - **Query systematically** to find relevant information that might answer the user's question
            3. **DECISION PROCESS** - Follow this order:
               a) **EXPLORE**: Use listing/discovery tools to understand what data you have access to
               b) **INVESTIGATE**: Query relevant data sources that might contain the requested information  
               c) **ANALYZE**: Examine the data to see if it answers any part of the user's question
               d) **RESPOND**: Only after genuine exploration, determine if you can provide partial or complete answers
            **Original User Query**: {user_query}
            """
    
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
                    verifier_response_str = self.extract_and_fix_json(str(verifier_response))
                    
                    if verifier_response_str and 'tool_error' in verifier_response_str:
                        tool_error = self.get_json_key(verifier_response_str, "tool_error")
                        if tool_error == "yes":
                            tool_name = self.get_json_key(verifier_response_str, "tool_name")
                            if tool_name:
                                await self._stream_update("content", f"Repeated errors when calling tool {tool_name}. Please reach out to System Administrator")
                                return {"type": ResponseType.ERROR.value, "content": f"Repeated errors when calling tool {tool_name}"}
                            else:
                                await self._stream_update("content", "Tool errors detected. Please reach out to System Administrator")
                                return {"type": ResponseType.ERROR.value, "content": "Tool errors detected"}
                    
                    can_answer = self.get_json_key(verifier_response_str, "can_answer") if verifier_response_str else None
                    if can_answer == 'yes':
                        # Generate business analysis report
                        summarize_response = quick_summarize(verifier_input, "", self.config.model.cheaper_model_id)
                        await self._stream_update("content",summarize_response,is_partial=False)
                        #summary_response = await self._generate_business_analysis_report(combined_response, user_query)
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
                if not session_id or session_id == "None":
                    session_id = f"session_{int(time.time())}"
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
                orchestrator_response = await self._get_orchestrator_response(additional_prompts)
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
                    "thinking",
                    f"Maximum iterations ({max_iterations}) reached. The query may not be fully resolved."
                )
                await self._stream_update("end", timestamp=datetime.now().isoformat())
                

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self._stream_update("content", f"Sorry, I encountered an error: {str(e)}", is_partial=False)

    def stop(self):
        """Stop the chatbot."""
        self.is_running = False
        print("🛑 Stopping chatbot...")

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
                tool_executed_name = None
                agent_resp = None
                if hasattr(result, 'message') and result.message:
                    # Fix: Access message attribute properly, not as dictionary
                    if 'content' in result.message and result.message['content']:
                        for payload in result.message['content']:
                            if 'toolUse' in payload:
                                tool_executed_name = payload['toolUse']['name']
                            if 'text' in payload:
                                agent_resp = payload['text']
                
                # Handle interrupts if they occur
                while result.stop_reason == "interrupt":
                    responses = []
                    agent_msg = f"Agent {agent_name} executed tool {tool_executed_name} and here is the output {agent_resp}"
                    responses.append({"agent_name": agent_name, "response": agent_msg})
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
                                    break
                            
                            if auto_approved:
                                continue
                            
                            # No auto-approval found, stream the approval request to the user
                            await self._stream_approval_request(interrupt)
                            
                            # Return the interrupt to be handled by the UI
                            # This follows the same pattern as orchestrator confirmation
                            return {
                                "type": "tool_approval_needed",
                                "interrupt_id": interrupt.id,
                                "reason": interrupt.reason,
                                "agent_name": agent_name,
                                "query": query,
                                "pending_responses": responses
                            }
                    
                    # This code should not be reached in the new flow
                    # but kept for backward compatibility
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
        
        approval_message = f"""
🔐 **Approval Required**
**Tool:** {reason.get('tool_name', 'Unknown')}
**Risk Level:** {reason.get('risk_level', 'Unknown').upper()}
**Summary:** {reason.get('summary', 'No summary available')}
**Details:**
"""
        for key, value in reason.get('details', {}).items():
            approval_message += f"- **{key.replace('_', ' ').title()}:** {value}\n"
            
        approval_message += "\n**Do you want to proceed with this operation?**"
        
        await self._stream_update("thinking", approval_message)

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

            # Send the HTML content to the frontend
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