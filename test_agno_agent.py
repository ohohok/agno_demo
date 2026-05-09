"""
Unit tests for Agno AI Chat Service
Tests the API endpoints and agent functionality
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file FIRST (before any other imports)
load_dotenv()

# Set test API key if not already set (priority: .env > test default)
if not os.getenv("ZHIPUAI_API_KEY"):
    os.environ["ZHIPUAI_API_KEY"] = "test-api-key-for-testing"

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Now import the application modules
from agno_agent import app, agno_agent, ChatRequest, ChatResponse


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def mock_agent_response():
    """Create a mock agent response"""
    mock_response = Mock()
    mock_response.content = "这是一个测试回复"
    mock_response.session_id = "test-session-123"
    mock_response.run_id = "test-run-456"
    return mock_response


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """Test that health endpoint returns healthy status"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Agno AI Chat"


class TestChatEndpoint:
    """Test chat endpoint"""

    @patch.object(agno_agent, 'run')
    def test_chat_with_message(self, mock_run, client, mock_agent_response):
        """Test basic chat functionality"""
        mock_run.return_value = mock_agent_response

        response = client.post(
            "/api/chat",
            json={"message": "你好"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "这是一个测试回复"
        assert data["session_id"] == "test-session-123"
        assert data["run_id"] == "test-run-456"

        # Verify agent.run was called with correct parameters
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == "你好"  # First positional arg is message

    @patch.object(agno_agent, 'run')
    def test_chat_with_user_id(self, mock_run, client, mock_agent_response):
        """Test chat with custom user_id"""
        mock_run.return_value = mock_agent_response

        response = client.post(
            "/api/chat",
            json={
                "message": "你好",
                "user_id": "custom-user-123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify user_id was passed correctly
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["user_id"] == "custom-user-123"

    @patch.object(agno_agent, 'run')
    def test_chat_with_session_id(self, mock_run, client, mock_agent_response):
        """Test chat with session_id for conversation continuity"""
        mock_run.return_value = mock_agent_response

        response = client.post(
            "/api/chat",
            json={
                "message": "继续之前的话题",
                "session_id": "existing-session-789"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify session_id was passed correctly
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["session_id"] == "existing-session-789"

    def test_chat_missing_message(self, client):
        """Test chat endpoint with missing message field"""
        response = client.post(
            "/api/chat",
            json={}
        )

        # Should return validation error (422)
        assert response.status_code == 422

    @patch.object(agno_agent, 'run')
    def test_chat_empty_message(self, mock_run, client, mock_agent_response):
        """Test chat with empty message"""
        mock_run.return_value = mock_agent_response

        response = client.post(
            "/api/chat",
            json={"message": ""}
        )

        # Empty message should still be processed
        assert response.status_code == 200

    @patch.object(agno_agent, 'run')
    def test_chat_long_message(self, mock_run, client, mock_agent_response):
        """Test chat with long message"""
        mock_run.return_value = mock_agent_response
        long_message = "这是一条很长的消息 " * 100

        response = client.post(
            "/api/chat",
            json={"message": long_message}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch.object(agno_agent, 'run')
    def test_chat_error_handling(self, mock_run, client):
        """Test error handling when agent fails"""
        mock_run.side_effect = Exception("Agent error")

        response = client.post(
            "/api/chat",
            json={"message": "测试错误处理"}
        )

        # Should return 500 error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    @patch.object(agno_agent, 'run')
    def test_chat_auto_knowledge(self, mock_run, client, mock_agent_response):
        """Test chat endpoint with automatic knowledge retrieval"""
        mock_run.return_value = mock_agent_response

        response = client.post(
            "/api/chat",
            json={
                "message": "测试知识库",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestChatRequestModel:
    """Test ChatRequest Pydantic model"""

    def test_chat_request_valid(self):
        """Test valid chat request"""
        request = ChatRequest(message="你好")
        assert request.message == "你好"
        assert request.user_id == "default_user"
        assert request.session_id is None

    def test_chat_request_with_optional_fields(self):
        """Test chat request with optional fields"""
        request = ChatRequest(
            message="你好",
            user_id="user123",
            session_id="session456",
        )
        assert request.message == "你好"
        assert request.user_id == "user123"
        assert request.session_id == "session456"

    def test_chat_request_missing_message(self):
        """Test chat request without required message field"""
        with pytest.raises(Exception):  # ValidationError
            ChatRequest()


class TestChatResponseModel:
    """Test ChatResponse Pydantic model"""

    def test_chat_response_valid(self):
        """Test valid chat response"""
        response = ChatResponse(
            success=True,
            message="回复内容",
            session_id="session123",
            run_id="run456"
        )
        assert response.success is True
        assert response.message == "回复内容"
        assert response.session_id == "session123"
        assert response.run_id == "run456"

    def test_chat_response_minimal(self):
        """Test minimal chat response"""
        response = ChatResponse(
            success=True,
            message="回复内容"
        )
        assert response.success is True
        assert response.message == "回复内容"
        assert response.session_id is None
        assert response.run_id is None
        assert response.knowledge_sources is None


class TestAgentConfiguration:
    """Test agent configuration"""

    def test_agent_has_correct_model(self):
        """Test that agent uses correct model"""
        assert agno_agent.model is not None
        assert hasattr(agno_agent.model, 'id')

    def test_agent_markdown_enabled(self):
        """Test that markdown is enabled"""
        assert agno_agent.markdown is True

    def test_agent_has_database(self):
        """Test that agent uses SQLite database"""
        assert agno_agent.db is not None

    def test_agent_no_tools(self):
        """Test that agent has no tools configured"""
        assert agno_agent.tools is None or len(agno_agent.tools) == 0


class TestIntegration:
    """Integration tests (require actual API key)"""

    @pytest.mark.skipif(
        not os.getenv("ZHIPUAI_API_KEY") or os.getenv("ZHIPUAI_API_KEY") == "test-api-key-for-testing",
        reason="Requires real ZHIPUAI_API_KEY"
    )
    def test_real_api_call(self, client):
        """Test with real API call (only runs with real API key)"""
        response = client.post(
            "/api/chat",
            json={"message": "你好，请简单回复"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["message"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
