"""
Centralized prompt templates for the data discovery agent system.
This module contains all the prompt templates used by various agents in the system.
"""

from typing import List, Dict, Any


class PromptTemplates:
    """Container class for all prompt templates used in the system."""
    
    @staticmethod
    def get_verifier_agent_prompt() -> str:
        """
        Prompt template for the verifier agent that checks if queries are resolved.
        
        Returns:
            str: The verifier agent system prompt
        """
        return """
        You are a Verifier agent, designed to check if the user query can be answered with the collected data.
        
        You will be given:
        - The original user query
        - Collected data from various specialist agents
        
        Your task is to determine if the collected data is sufficient to answer the user's query.
        
        **Output Format - MANDATORY JSON:**
        {
            "can_answer": "yes" or "no",
            "tool_error": "yes" or "no",
            "tool_name": "name of tool that had error (if tool_error is yes)",
            "reasoning": "Brief explanation of your decision"
        }
        
        **Decision Criteria:**
        - "can_answer": "yes" if the collected data sufficiently addresses the user's query
        - "can_answer": "no" if more data is needed or the query cannot be answered
        - "tool_error": "yes" if you detect any tool execution errors in the data
        - "tool_error": "no" if no tool errors are detected
        
        MANDATORY: You will only return a valid JSON object and nothing else.
        """
    
    @staticmethod
    def get_orchestrator_agent_prompt(available_agents: List[Dict[str, Any]], max_iterations: int = 5, agent_interactions_header: str='', agent_interactions: str='') -> str:
        """
        Prompt template for the orchestrator agent that coordinates multiple agents.
        
        Args:
            available_agents: List of available agent configurations
            max_iterations: Maximum number of iterations before seeking user clarification
            agent_interactions_header: Optional header for agent interactions section
            agent_interactions: Optional agent interactions content
            
        Returns:
            str: The orchestrator agent system prompt
        """
        agents_info = ', '.join([
            f"Agent: {client['name'].lower()}, MCP_Agent: yes, Type: {client['agent_type']}, "
            f"Description: {client['description']} {client['usage']}" 
            for client in available_agents
        ])
        
        return f"""
        You are a Multi-Agent Orchestrator designed to coordinate support across multiple specialist agents.
        
        **Available Agents:**
        {agents_info}
        
        **Your Role:**
        1. As an orchestrator analyze user queries and determine the most appropriate agents to handle them
        2. Create execution plans with ordered agent calls.
        3. The Orchestrator should try creating a plan {max_iterations} times after which it should seek clarification from the User

        {agent_interactions_header}
        {agent_interactions}
        
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
        
        **Agent Exploration Checklist (before calling User):**
        - [ ] Attempted all database agents that might contain relevant data?
        - [ ] Tried agents with overlapping capabilities?
        - [ ] Considered unconventional but potentially relevant agents?
        - [ ] Attempted combination approaches?
        
        REMEMBER: Be resourceful and thorough. User clarification should demonstrate you've exhausted technical solutions.
        """
    
    @staticmethod
    def get_specialized_agent_prompt() -> str:
        """
        Prompt template for specialized agents that work with specific tools.
        
        Returns:
            str: The specialized agent system prompt template
        """
        return """
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
    
    @staticmethod
    def get_enhanced_query(user_query: str) -> str:
        """
        Build enhanced query prompt with context from previous agent responses.
        
        Args:
            user_query: The original user query
            agent_responses: List of responses from previous agents
            
        Returns:
            str: Enhanced query prompt with context
        """
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
    
    @staticmethod
    def get_enhanced_query_without_context(user_query: str) -> str:
        """
        Build enhanced query prompt without previous context.
        
        Args:
            user_query: The original user query
            
        Returns:
            str: Enhanced query prompt without context
        """
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


# Convenience functions for backward compatibility
def get_verifier_prompt() -> str:
    """Get the verifier agent prompt."""
    return PromptTemplates.get_verifier_agent_prompt()


def get_orchestrator_prompt(available_agents: List[Dict[str, Any]], max_iterations: int = 5) -> str:
    """Get the orchestrator agent prompt."""
    return PromptTemplates.get_orchestrator_agent_prompt(available_agents, max_iterations)


def get_specialized_agent_prompt() -> str:
    """Get the specialized agent prompt template."""
    return PromptTemplates.get_specialized_agent_prompt()


def build_enhanced_query(user_query: str, agent_responses: List[Dict] = None) -> str:
    """Build enhanced query with or without context."""
    if agent_responses and len(agent_responses) > 0:
        return PromptTemplates.get_enhanced_query_with_context(user_query, agent_responses)
    else:
        return PromptTemplates.get_enhanced_query_without_context(user_query)