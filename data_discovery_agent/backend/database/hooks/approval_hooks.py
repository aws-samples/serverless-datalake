"""
Approval hooks for MCP tool calls that require human confirmation.
Intercepts specific tool calls and requests user approval before execution.
"""

import logging
from typing import Dict, Any, List
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

logger = logging.getLogger(__name__)

# Global approval cache to store temporary approvals
_approval_cache = {}

# Global "always approve" cache for specific tools
_always_approve_cache = {}

#approval_response is always/approve/deny
def set_tool_approval(interrupt_id: str, tool_name: str, approval_response: str):
    """Set a temporary tool approval in the global cache."""
    global _approval_cache, _always_approve_cache
    _approval_cache[interrupt_id] = {
        'tool_name': tool_name,
        'response': approval_response
    }
    
    # If this is an "always" approval, also store it in the always approve cache
    if approval_response.lower() in ["always", "a"]:
        _always_approve_cache[tool_name] = True
        logger.info(f"Added tool {tool_name} to always approve cache")

def set_always_approve_for_tool(tool_name: str):
    """Set a tool to always be approved without asking."""
    global _always_approve_cache
    _always_approve_cache[tool_name] = True
    logger.info(f"Tool {tool_name} set to always approve")

def remove_always_approve_for_tool(tool_name: str):
    """Remove a tool from the always approve list."""
    global _always_approve_cache
    if tool_name in _always_approve_cache:
        del _always_approve_cache[tool_name]
        logger.info(f"Tool {tool_name} removed from always approve cache")

def is_tool_always_approved(tool_name: str) -> bool:
    """Check if a tool is in the always approve cache."""
    global _always_approve_cache
    return _always_approve_cache.get(tool_name, False)

def get_always_approved_tools() -> List[str]:
    """Get list of all tools that are always approved."""
    global _always_approve_cache
    return list(_always_approve_cache.keys())

def clear_tool_approval(interrupt_id: str):
    """Clear a temporary tool approval from the global cache."""
    global _approval_cache
    if interrupt_id in _approval_cache:
        del _approval_cache[interrupt_id]


class MCPToolApprovalHook(HookProvider):
    """
    Approval hook for MCP tool calls that require human confirmation.
    Intercepts specific tool calls and requests user approval before execution.
    """
    
    def __init__(self, app_name: str, tools_requiring_approval: List[str] = None, 
                 auto_approve_patterns: List[str] = None):
        """
        Initialize the approval hook.
        
        Args:
            app_name: Name of the application for interrupt identification
            tools_requiring_approval: List of tool names that require approval
            auto_approve_patterns: List of patterns that can be auto-approved
        """
        self.app_name = app_name
        self.tools_requiring_approval = tools_requiring_approval
        # self.auto_approve_patterns = auto_approve_patterns or [
        #     "list", "get", "describe", "read"
        # ]
        self.auto_approve_patterns = auto_approve_patterns or [
            "lrtaws"
        ]
        
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the approval hook for BeforeToolCallEvent."""
        registry.add_callback(BeforeToolCallEvent, self.approve_tool_call)
        
    def approve_tool_call(self, event: BeforeToolCallEvent) -> None:
        """
        Intercept tool calls and request approval for sensitive tools.
        
        Args:
            event: The BeforeToolCallEvent containing tool call information
        """
        tool_name = event.tool_use.get("name", "")
        tool_input = event.tool_use.get("input", {})
        
        # Skip if tool doesn't require approval
        if not self._requires_approval(tool_name, tool_input):
            return
        
        # Check global always approve cache first
        if is_tool_always_approved(tool_name):
            logger.info(f"Tool {tool_name} is in always approve cache, skipping approval")
            return
            
        # Check if already approved in session state
        approval_key = f"{self.app_name}-{tool_name}-approval"
        if event.agent.state.get(approval_key) == "approved":
            return
            
        # Check global approval cache for temporary approvals
        global _approval_cache
        for interrupt_id, approval_data in list(_approval_cache.items()):
            # Check if this approval applies to this tool or is a general approval
            if (approval_data.get('tool_name') in [tool_name, "any"] and 
                self._is_approved(approval_data.get('response', ''))):
                # Remove from cache after use (unless it's "always")
                if approval_data.get('response', '').lower() not in ["always", "a"]:
                    del _approval_cache[interrupt_id]
                else:
                    # Store in session state for "always" approvals
                    event.agent.state.set(approval_key, "approved")
                    # Also add to global always approve cache
                    set_always_approve_for_tool(tool_name)
                return
            
        # Create approval request with detailed information
        approval_reason = self._create_approval_reason(tool_name, tool_input)
        
        # Request human approval
        approval_response = event.interrupt(
            f"{self.app_name}-tool-approval",
            reason=approval_reason
        )
        
        # Process approval response
        if not self._is_approved(approval_response):
            event.cancel_tool = f"User denied permission to execute {tool_name}"
            return
            
        # Store approval in session state for future calls
        if approval_response.lower() in ["always", "a"]:
            event.agent.state.set(approval_key, "approved")
            # Also add to global always approve cache
            set_always_approve_for_tool(tool_name)
            
    def _requires_approval(self, tool_name: str, tool_input: Dict[str, Any]) -> bool:
        """
        Determine if a tool call requires approval.
        
        Args:
            tool_name: Name of the tool being called
            tool_input: Input parameters for the tool
            
        Returns:
            True if approval is required, False otherwise
        """
        return True
        
        for pattern in self.auto_approve_patterns:
            if pattern in tool_name.lower():
                return False
        
        # Check if any partial name from tools_requiring_approval exists in tool_name
        if self.tools_requiring_approval:
            for partial_name in self.tools_requiring_approval:
                if partial_name.lower() in tool_name.lower():
                    return True

        return True
        
    def _create_approval_reason(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a detailed approval reason for the user.
        
        Args:
            tool_name: Name of the tool being called
            tool_input: Input parameters for the tool
            
        Returns:
            Dictionary containing approval reason details
        """
        reason = {
            "tool_name": tool_name,
            "summary": f"Request to execute {tool_name}",
            "details": {},
            "tool_input": tool_input,  # Store the actual tool input parameters
            "tool_parameters": tool_input  # Also store as tool_parameters for UI display
        }
        # Add all tool input parameters to details for comprehensive display
        # This ensures all parameters are visible in the UI
        # for key, value in tool_input.items():
        #     if key not in reason["details"]:  # Don't override specific details we've already set
        #         reason["details"][key] = value
                
        # Add risk assessment
        risk_level = self._assess_risk_level(tool_name, tool_input)
        reason["risk_level"] = risk_level
        
        return reason
        
    def _assess_risk_level(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Assess the risk level of the tool_name.
        
        Args:
            tool_name: The tool being accessed
            tool_input: Input parameters for the tool
            
        Returns:
            Risk level as string (low, medium, high)
        """
        high_risk_tools = ["delete", "drop", "terminate", "stop", "kill", "execute"]
        medium_risk_tools = ["create", "update", "modify", "start"]
        
        tool_name = tool_name.lower()
        
        if any(op in tool_name for op in high_risk_tools):
            return "high"
        elif any(op in tool_name for op in medium_risk_tools):
            return "medium"
        else:
            return "low"
            
    def _is_approved(self, response: str) -> bool:
        """
        Check if the user approved the tool_name.
        
        Args:
            response: User's response to the approval request
            
        Returns:
            True if approved, False otherwise
        """
        if not response:
            return False
            
        response_lower = response.lower().strip()
        approved_responses = ["y", "yes", "approve", "ok", "always", "a"]
        
        return response_lower in approved_responses