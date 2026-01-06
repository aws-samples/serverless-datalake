# Configuration System

This directory contains the configuration system for the MCP Data Discovery Agent. The configuration system allows you to customize various aspects of the chatbot's behavior, from model settings to processing parameters.

## Files

- `chatbot_config.py` - Main configuration classes and logic
- `config_template.json` - Template configuration file you can customize
- `example_usage.py` - Examples of how to use the configuration system
- `README.md` - This file

## Configuration Structure

The configuration is organized into several sections:

### Model Configuration
Controls AI model settings:
```json
{
  "model": {
    "primary_model_id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "cheaper_model_id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "max_tokens": 4000,
    "temperature": 0.1
  }
}
```

### Session Configuration
Controls conversation and session management:
```json
{
  "session": {
    "session_timeout_minutes": 60,
    "max_conversation_length": 100,
    "enable_summarization": true,
    "summarization_threshold": 50
  }
}
```

### Processing Configuration
Controls query processing behavior:
```json
{
  "processing": {
    "max_iterations": 5,
    "require_human_confirmation": true,
    "enable_parallel_execution": false,
    "timeout_seconds": 300
  }
}
```

### Dashboard Configuration
Controls dashboard generation:
```json
{
  "dashboard": {
    "output_directory": "generated_dashboards",
    "enable_export": true,
    "default_chart_library": "chartjs",
    "max_datasets": 10
  }
}
```

## Usage Methods

### 1. Default Configuration
The simplest way - uses built-in defaults:

```python
from database.database_mcp_clients import MCPClientChatbot

chatbot = MCPClientChatbot(sse_urls=your_servers)
```

### 2. Custom Configuration Object
Create a custom configuration programmatically:

```python
from config.chatbot_config import ChatbotConfig, ProcessingConfig
from database.database_mcp_clients import MCPClientChatbot

config = ChatbotConfig(
    processing=ProcessingConfig(
        max_iterations=3,
        require_human_confirmation=False  # Auto-execute plans
    )
)

chatbot = MCPClientChatbot(sse_urls=your_servers, config=config)
```

### 3. Configuration from File
Load configuration from a JSON file:

```python
from config.chatbot_config import ChatbotConfig
from database.database_mcp_clients import MCPClientChatbot

config = ChatbotConfig.from_file('my_config.json')
chatbot = MCPClientChatbot(sse_urls=your_servers, config=config)
```

### 4. Configuration from Environment Variables
Load configuration from environment variables:

```python
from config.chatbot_config import ChatbotConfig
from database.database_mcp_clients import MCPClientChatbot

config = ChatbotConfig.from_env()
chatbot = MCPClientChatbot(sse_urls=your_servers, config=config)
```

### 5. Runtime Configuration Updates
Update configuration while the chatbot is running:

```python
# Update configuration at runtime
new_config = ChatbotConfig(
    processing=ProcessingConfig(max_iterations=10)
)
chatbot.update_config(new_config)
```

## Configuration Options Explained

### Key Settings

**require_human_confirmation** (default: `true`)
- `true`: Plans are presented to users for approval before execution
- `false`: Plans are executed automatically without user confirmation

**max_iterations** (default: `5`)
- Maximum number of retry attempts for query resolution
- Higher values allow more thorough exploration but may take longer

**enable_summarization** (default: `true`)
- `true`: Long conversations are automatically summarized to save context
- `false`: Full conversation history is maintained (may hit token limits)

**max_datasets** (default: `10`)
- Maximum number of datasets to collect for dashboard generation
- Lower values improve performance but may miss relevant data

**output_directory** (default: `"generated_dashboards"`)
- Directory where generated dashboards are saved
- Can be customized for different environments

## Environment Variables

You can override configuration using environment variables:

```bash
export PRIMARY_MODEL_ID="global.anthropic.claude-sonnet-4-5-20250929-v1:0"
export MAX_ITERATIONS="3"
export REQUIRE_CONFIRMATION="false"
export LOG_LEVEL="DEBUG"
export DEBUG_MODE="true"
```

## API Endpoints

The Flask application provides endpoints to manage configuration:

- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration

## Best Practices

1. **Start with defaults** - Use the default configuration initially
2. **Customize gradually** - Override only the settings you need to change
3. **Use files for production** - Store production configurations in JSON files
4. **Version control configs** - Keep configuration files in version control
5. **Test configuration changes** - Verify changes work as expected before deploying

## Example Configurations

### Development Configuration
```json
{
  "processing": {
    "max_iterations": 3,
    "require_human_confirmation": false
  },
  "log_level": "DEBUG",
  "debug_mode": true
}
```

### Production Configuration
```json
{
  "processing": {
    "max_iterations": 5,
    "require_human_confirmation": true,
    "timeout_seconds": 600
  },
  "session": {
    "enable_summarization": true,
    "session_timeout_minutes": 120
  },
  "dashboard": {
    "output_directory": "production_dashboards",
    "max_datasets": 15
  },
  "log_level": "INFO",
  "debug_mode": false
}
```

### High-Performance Configuration
```json
{
  "processing": {
    "max_iterations": 7,
    "require_human_confirmation": false,
    "enable_parallel_execution": true
  },
  "session": {
    "enable_summarization": false
  },
  "dashboard": {
    "max_datasets": 20
  }
}
```