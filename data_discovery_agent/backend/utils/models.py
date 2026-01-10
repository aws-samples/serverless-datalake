"""
Common data models and utility classes for the data discovery agent system.
This module contains shared classes used across different components.
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class ResponseType(Enum):
    """Enum for different response types."""
    SUCCESS = "success"
    ERROR = "error"
    CLARIFICATION = "clarification"
    CONFIRMATION_NEEDED = "confirmation_needed"
    SQL_CONFIRMATION_NEEDED = "sql_confirmation_needed"
    TOOL_APPROVAL_NEEDED = "tool_approval_needed"
    PARTIAL = "partial"
    # DASHBOARD_FILE = "dashboard_file"
    # WIDGET_FILE = "widget_file"
    # HTML_CONTENT = "html_content"
    WITH_CITATIONS = "with_citations"


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


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_data)