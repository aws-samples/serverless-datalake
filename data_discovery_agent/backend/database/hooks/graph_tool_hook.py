"""
Graph tool hooks for MCP tool call result processing.
Intercepts tool call results for logging and analysis purposes.
"""

import logging
from typing import Dict, Any, List
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry, AfterToolCallEvent

logger = logging.getLogger(__name__)

class GraphToolHook(HookProvider):
    """
    Hook for capturing and processing MCP tool call results.
    Intercepts tool call results for logging and analysis.
    """
    
    def __init__(self):
        """Initialize the graph tool hook."""
        pass
        
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the hook for AfterToolCallEvent."""
        registry.add_callback(AfterToolCallEvent, self.fetch_tool_call_result)
    
    def fetch_tool_call_result(self, event: AfterToolCallEvent) -> None:
        """Process tool call results after execution."""
        logger.info(f"Tool call completed: {event.tool_use.get('name', 'unknown')}")
        # Add any additional processing logic here