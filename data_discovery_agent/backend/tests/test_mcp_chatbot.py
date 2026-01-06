"""
Unit tests for the MCP Chatbot system.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any

# Import your classes (adjust imports as needed)
from database.improved_database_mcp_clients import (
    ImprovedMCPChatbot, MCPServerConfig, AgentResponse, 
    ResponseType, MCPClientManager, AgentFactory
)

class TestMCPServerConfig:
    """Test MCPServerConfig dataclass."""
    
    def test_config_creation(self):
        """Test basic config creation."""
        config = MCPServerConfig(
            name="test_server",
            agent_type="database",
            description="Test server",
            url="http://localhost:8000"
        )
        
        assert config.name == "test_server"
        assert config.agent_type == "database"
        assert config.args == []  # Default value
    
    def test_config_with_args(self):
        """Test config with command args."""
        config = MCPServerConfig(
            name="stdio_server",
            agent_type="analytics",
            description="STDIO server",
            command="python",
            args=["script.py", "--verbose"]
        )
        
        assert config.command == "python"
        assert config.args == ["script.py", "--verbose"]

class TestAgentResponse:
    """Test AgentResponse dataclass."""
    
    def test_successful_response(self):
        """Test successful agent response."""
        response = AgentResponse(
            agent_name="TestAgent",
            response="Success data",
            success=True
        )
        
        assert response.agent_name == "TestAgent"
        assert response.success is True
        assert response.metadata == {}  # Default value
    
    def test_error_response(self):
        """Test error agent response."""
        response = AgentResponse(
            agent_name="TestAgent",
            response="",
            success=False,
            error_message="Connection failed"
        )
        
        assert response.success is False
        assert response.error_message == "Connection failed"

class TestMCPClientManager:
    """Test MCPClientManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create MCPClientManager instance."""
        return MCPClientManager()
    
    @pytest.fixture
    def mock_config(self):
        """Create mock server config."""
        return MCPServerConfig(
            name="test_server",
            agent_type="database",
            description="Test server",
            url="http://localhost:8000"
        )
    
    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert isinstance(manager.clients, dict)
        assert len(manager.clients) == 0
    
    @patch('database.improved_database_mcp_clients.MCPClient')
    @patch('database.improved_database_mcp_clients.sse_client')
    def test_register_client_success(self, mock_sse_client, mock_mcp_client, manager, mock_config):
        """Test successful client registration."""
        # Mock the MCP client and tools
        mock_client_instance = Mock()
        mock_client_instance.list_tools_sync.return_value = [
            Mock(tool_name="test_tool", tool_spec={
                "description": "Test tool",
                "inputSchema": {"type": "object"}
            })
        ]
        mock_mcp_client.return_value.__enter__.return_value = mock_client_instance
        
        # Register client
        success = manager.register_client(mock_config)
        
        assert success is True
        assert "test_server" in manager.clients
        assert len(manager.clients["test_server"]["tools"]) == 1
    
    def test_get_nonexistent_client(self, manager):
        """Test getting non-existent client."""
        client = manager.get_client("nonexistent")
        assert client is None
    
    def test_get_tools_nonexistent(self, manager):
        """Test getting tools for non-existent client."""
        tools = manager.get_tools("nonexistent")
        assert tools == []

class TestImprovedMCPChatbot:
    """Test ImprovedMCPChatbot class."""
    
    @pytest.fixture
    def chatbot(self):
        """Create chatbot instance."""
        return ImprovedMCPChatbot()
    
    @pytest.fixture
    def mock_server_configs(self):
        """Create mock server configurations."""
        return [
            MCPServerConfig(
                name="athena",
                agent_type="database",
                description="Athena service",
                url="http://localhost:8000"
            ),
            MCPServerConfig(
                name="redis",
                agent_type="cache",
                description="Redis service",
                command="redis-cli"
            )
        ]
    
    def test_chatbot_initialization(self, chatbot):
        """Test chatbot initialization."""
        assert chatbot.model is not None
        assert chatbot.mcp_manager is not None
        assert chatbot.collected_datasets == []
        assert chatbot.total_datasets == 0
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, chatbot, mock_server_configs):
        """Test successful chatbot initialization."""
        with patch.object(chatbot.mcp_manager, 'register_client', return_value=True):
            with patch.object(chatbot, '_create_core_agents', new_callable=AsyncMock):
                success = await chatbot.initialize(mock_server_configs)
                
                assert success is True
                assert chatbot.session_manager is not None
                assert chatbot.conversation_manager is not None
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self, chatbot, mock_server_configs):
        """Test chatbot initialization failure."""
        with patch.object(chatbot.mcp_manager, 'register_client', side_effect=Exception("Connection failed")):
            success = await chatbot.initialize(mock_server_configs)
            
            assert success is False
    
    def test_extract_json_data_valid(self, chatbot):
        """Test JSON extraction from valid text."""
        text = 'Some text {"data": [{"key": "value"}]} more text'
        result = chatbot._extract_json_data(text)
        
        assert result is not None
        assert result["data"][0]["key"] == "value"
    
    def test_extract_json_data_invalid(self, chatbot):
        """Test JSON extraction from invalid text."""
        text = "No JSON here"
        result = chatbot._extract_json_data(text)
        
        assert result is None
    
    def test_needs_human_confirmation_simple(self, chatbot):
        """Test human confirmation for simple plan."""
        plan = [{"agent_name": "athena", "step_number": 1}]
        needs_confirmation = chatbot._needs_human_confirmation(plan)
        
        # Current implementation always requires confirmation for multi-step plans
        assert needs_confirmation is False  # Single step
    
    def test_needs_human_confirmation_complex(self, chatbot):
        """Test human confirmation for complex plan."""
        plan = [
            {"agent_name": "athena", "step_number": 1},
            {"agent_name": "redis", "step_number": 2}
        ]
        needs_confirmation = chatbot._needs_human_confirmation(plan)
        
        assert needs_confirmation is True  # Multi-step
    
    def test_needs_human_confirmation_user_step(self, chatbot):
        """Test human confirmation when user input needed."""
        plan = [{"agent_name": "User", "clarification_message": "Need info"}]
        needs_confirmation = chatbot._needs_human_confirmation(plan)
        
        assert needs_confirmation is True
    
    def test_build_enhanced_query_no_context(self, chatbot):
        """Test query building without previous context."""
        query = "Show me sales data"
        enhanced = chatbot._build_enhanced_query(query, [])
        
        assert "Original Query: Show me sales data" in enhanced
        assert "multi-agent system" in enhanced
    
    def test_build_enhanced_query_with_context(self, chatbot):
        """Test query building with previous context."""
        query = "Show me sales data"
        previous_responses = [
            AgentResponse("athena", "Found 100 records", True),
            AgentResponse("redis", "Cache miss", True)
        ]
        
        enhanced = chatbot._build_enhanced_query(query, previous_responses)
        
        assert "Previous Agent Responses:" in enhanced
        assert "athena" in enhanced
        assert "Found 100 records" in enhanced
    
    @pytest.mark.asyncio
    async def test_stream_update_with_callback(self, chatbot):
        """Test streaming update with callback."""
        callback_data = []
        
        async def mock_callback(data):
            callback_data.append(data)
        
        chatbot.stream_callback = mock_callback
        
        await chatbot._stream_update("thinking", "Processing...", True)
        
        assert len(callback_data) == 1
        assert callback_data[0]["type"] == "thinking"
        assert callback_data[0]["content"] == "Processing..."
        assert callback_data[0]["is_partial"] is True
    
    @pytest.mark.asyncio
    async def test_stream_update_no_callback(self, chatbot):
        """Test streaming update without callback."""
        # Should not raise exception
        await chatbot._stream_update("thinking", "Processing...")
        
        # No assertions needed - just ensure no exception

class TestIntegration:
    """Integration tests for the complete system."""
    
    @pytest.mark.asyncio
    async def test_full_query_processing_flow(self):
        """Test complete query processing flow."""
        # This would be a more complex integration test
        # involving mocked MCP servers and agents
        pass
    
    @pytest.mark.asyncio
    async def test_dashboard_generation_flow(self):
        """Test dashboard generation flow."""
        # Test the complete dashboard generation process
        pass
    
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self):
        """Test error recovery and retry mechanisms."""
        pass

# Fixtures for common test data
@pytest.fixture
def sample_agent_responses():
    """Sample agent responses for testing."""
    return [
        AgentResponse("athena", '{"data": [{"sales": 1000}]}', True),
        AgentResponse("redis", '{"cache_hits": 50}', True),
        AgentResponse("failed_agent", "", False, "Connection timeout")
    ]

@pytest.fixture
def sample_orchestrator_plan():
    """Sample orchestrator plan for testing."""
    return [
        {"agent_name": "athena", "step_number": 1},
        {"agent_name": "redis", "step_number": 2},
        {"agent_name": "DashboardBuilder", "step_number": 3}
    ]

# Performance tests
class TestPerformance:
    """Performance-related tests."""
    
    @pytest.mark.asyncio
    async def test_concurrent_query_processing(self):
        """Test handling multiple concurrent queries."""
        # Test system behavior under load
        pass
    
    def test_memory_usage_with_large_datasets(self):
        """Test memory usage with large datasets."""
        # Test memory efficiency
        pass

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])