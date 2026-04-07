"""Shared test fixtures and configuration."""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key-for-unit-tests")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture
def mock_llm_response():
    """Return a mock LLM response with configurable content."""
    def _make_response(content: str):
        mock = MagicMock()
        mock.content = content
        return mock
    return _make_response


@pytest.fixture
def mock_search_results():
    """Return sample structured search results."""
    return [
        {"title": "AI Overview", "href": "https://example.com/ai", "body": "AI is transforming technology."},
        {"title": "Machine Learning Guide", "href": "https://example.com/ml", "body": "ML is a subset of AI."},
        {"title": "Deep Learning Tutorial", "href": "https://example.com/dl", "body": "Deep learning uses neural networks."},
    ]
