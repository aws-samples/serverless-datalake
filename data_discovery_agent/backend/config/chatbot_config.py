"""
Configuration management for the MCP Chatbot.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
from pathlib import Path

@dataclass
class ModelConfig:
    """Configuration for AI models."""
    #global.anthropic.claude-sonnet-4-5-20250929-v1:0
    primary_model_id: str = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    cheaper_model_id: str = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    max_tokens: int = 4000
    temperature: float = 0.1

@dataclass
class SessionConfig:
    """Configuration for session management."""
    session_timeout_minutes: int = 60
    max_conversation_length: int = 100
    enable_summarization: bool = True
    summarization_threshold: int = 50

@dataclass
class ProcessingConfig:
    """Configuration for query processing."""
    max_iterations: int = 5
    require_human_confirmation: bool = True
    enable_parallel_execution: bool = False
    timeout_seconds: int = 300
    
    # Approval settings for tool execution
    auto_approve_low_risk: bool = True
    auto_approve_medium_risk: bool = False
    auto_approve_high_risk: bool = False
    approval_timeout_seconds: int = 300

@dataclass
class DashboardConfig:
    """Configuration for dashboard generation."""
    output_directory: str = "generated_dashboards"
    enable_export: bool = True
    default_chart_library: str = "chartjs"
    max_datasets: int = 10

@dataclass
class ChatbotConfig:
    """Main configuration class."""
    model: ModelConfig = field(default_factory=ModelConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    
    # Environment-specific settings
    log_level: str = "INFO"
    debug_mode: bool = False
    
    @classmethod
    def from_file(cls, config_path: str) -> 'ChatbotConfig':
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            return cls(
                model=ModelConfig(**data.get('model', {})),
                session=SessionConfig(**data.get('session', {})),
                processing=ProcessingConfig(**data.get('processing', {})),
                dashboard=DashboardConfig(**data.get('dashboard', {})),
                log_level=data.get('log_level', 'INFO'),
                debug_mode=data.get('debug_mode', False)
            )
        except Exception as e:
            print(f"Error loading config from {config_path}: {e}")
            return cls()  # Return default config
    
    @classmethod
    def from_env(cls) -> 'ChatbotConfig':
        """Load configuration from environment variables."""
        return cls(
            model=ModelConfig(
                primary_model_id=os.getenv('PRIMARY_MODEL_ID', ModelConfig.primary_model_id),
                cheaper_model_id=os.getenv('CHEAPER_MODEL_ID', ModelConfig.cheaper_model_id),
                max_tokens=int(os.getenv('MAX_TOKENS', ModelConfig.max_tokens)),
                temperature=float(os.getenv('TEMPERATURE', ModelConfig.temperature))
            ),
            session=SessionConfig(
                session_timeout_minutes=int(os.getenv('SESSION_TIMEOUT', SessionConfig.session_timeout_minutes)),
                max_conversation_length=int(os.getenv('MAX_CONVERSATION_LENGTH', SessionConfig.max_conversation_length))
            ),
            processing=ProcessingConfig(
                max_iterations=int(os.getenv('MAX_ITERATIONS', ProcessingConfig.max_iterations)),
                require_human_confirmation=os.getenv('REQUIRE_CONFIRMATION', 'true').lower() == 'true',
                auto_approve_low_risk=os.getenv('AUTO_APPROVE_LOW_RISK', 'true').lower() == 'true',
                auto_approve_medium_risk=os.getenv('AUTO_APPROVE_MEDIUM_RISK', 'false').lower() == 'true',
                auto_approve_high_risk=os.getenv('AUTO_APPROVE_HIGH_RISK', 'false').lower() == 'true'
            ),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            debug_mode=os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        )
    
    def to_file(self, config_path: str):
        """Save configuration to JSON file."""
        config_data = {
            'model': {
                'primary_model_id': self.model.primary_model_id,
                'cheaper_model_id': self.model.cheaper_model_id,
                'max_tokens': self.model.max_tokens,
                'temperature': self.model.temperature
            },
            'session': {
                'session_timeout_minutes': self.session.session_timeout_minutes,
                'max_conversation_length': self.session.max_conversation_length,
                'enable_summarization': self.session.enable_summarization,
                'summarization_threshold': self.session.summarization_threshold
            },
            'processing': {
                'max_iterations': self.processing.max_iterations,
                'require_human_confirmation': self.processing.require_human_confirmation,
                'enable_parallel_execution': self.processing.enable_parallel_execution,
                'timeout_seconds': self.processing.timeout_seconds,
                'auto_approve_low_risk': self.processing.auto_approve_low_risk,
                'auto_approve_medium_risk': self.processing.auto_approve_medium_risk,
                'auto_approve_high_risk': self.processing.auto_approve_high_risk,
                'approval_timeout_seconds': self.processing.approval_timeout_seconds
            },
            'dashboard': {
                'output_directory': self.dashboard.output_directory,
                'enable_export': self.dashboard.enable_export,
                'default_chart_library': self.dashboard.default_chart_library,
                'max_datasets': self.dashboard.max_datasets
            },
            'log_level': self.log_level,
            'debug_mode': self.debug_mode
        }
        
        # Ensure directory exists
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)

# Default configuration instance
DEFAULT_CONFIG = ChatbotConfig()