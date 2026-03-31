"""Tests for node logic — planner JSON parsing, writer feedback integration, researcher source handling."""
import json
import pytest
from unittest.mock import MagicMock, patch


class TestPlannerJsonParsing:
    """Verify all 3 fallback strategies for parsing LLM research steps output."""

    def test_parse_clean_json(self):
        """Happy path: LLM returns clean JSON."""
        from src.nodes import planner_node
        mock_response = MagicMock()
        mock_response.content = json.dumps({"research_steps": ["Step 1", "Step 2", "Step 3"]})

        with patch("src.nodes.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = mock_response
            result = planner_node({"topic": "AI", "messages": []})
            assert result["research_steps"] == ["Step 1", "Step 2", "Step 3"]

    def test_parse_json_in_code_block(self):
        """Fallback 1: LLM wraps JSON in ```json ... ``` markers."""
        from src.nodes import planner_node
        mock_response = MagicMock()
        mock_response.content = '```json\n{"research_steps": ["A", "B"]}\n```'

        with patch("src.nodes.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = mock_response
            result = planner_node({"topic": "AI", "messages": []})
            assert result["research_steps"] == ["A", "B"]

    def test_parse_json_in_plain_code_block(self):
        """Fallback 2: LLM wraps JSON in ``` ... ``` without 'json' tag."""
        from src.nodes import planner_node
        mock_response = MagicMock()
        mock_response.content = '```\n{"research_steps": ["X", "Y"]}\n```'

        with patch("src.nodes.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = mock_response
            result = planner_node({"topic": "AI", "messages": []})
            assert result["research_steps"] == ["X", "Y"]

    def test_parse_numbered_lines_fallback(self):
        """Fallback 3: LLM returns numbered lines instead of JSON."""
        from src.nodes import planner_node
        mock_response = MagicMock()
        mock_response.content = "1. First step\n2. Second step\n3. Third step"

        with patch("src.nodes.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = mock_response
            result = planner_node({"topic": "AI", "messages": []})
            assert len(result["research_steps"]) == 3
            assert "First step" in result["research_steps"][0]

    def test_empty_response_uses_fallback(self):
        """When LLM returns empty content, use default steps."""
        from src.nodes import planner_node
        mock_response = MagicMock()
        mock_response.content = ""

        with patch("src.nodes.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = mock_response
            result = planner_node({"topic": "quantum computing", "messages": []})
            assert len(result["research_steps"]) > 0  # Falls back to defaults

    def test_content_filter_error(self):
        """DashScope content filter returns error state, not crash."""
        from src.nodes import planner_node
        from openai import BadRequestError

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {}

        with patch("src.nodes.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.side_effect = BadRequestError(
                message="data_inspection_failed",
                response=mock_resp,
                body={"message": "data_inspection_failed", "code": "DataInspectionFailed"}
            )
            result = planner_node({"topic": "AI", "messages": []})
            assert "error_message" in result
            assert "CONTENT_FILTER" in result["error_message"]


class TestResearcherSourceHandling:
    """Verify researcher_node correctly collects and deduplicates sources."""

    def test_structured_source_collection(self):
        """Search results (list of dicts) are collected as sources."""
        from src.nodes import researcher_node

        search_results = [
            {"title": "AI Overview", "href": "https://example.com/ai", "body": "AI is..."},
            {"title": "ML Guide", "href": "https://example.com/ml", "body": "ML is..."},
        ]

        with patch("src.nodes.search_tool") as mock_search:
            mock_search.invoke.return_value = search_results
            result = researcher_node({
                "research_steps": ["step1"],
                "messages": [],
                "sources": [],
                "user_feedback": "auto",  # Skip output guardrails
            })
            assert len(result["sources"]) == 2
            assert result["sources"][0]["title"] == "AI Overview"

    def test_source_deduplication(self):
        """Duplicate sources should not appear twice."""
        from src.nodes import researcher_node

        search_results = [
            {"title": "Same", "href": "https://example.com", "body": "same body"},
            {"title": "Same", "href": "https://example.com", "body": "same body"},
        ]

        with patch("src.nodes.search_tool") as mock_search:
            mock_search.invoke.return_value = search_results
            result = researcher_node({
                "research_steps": ["step1"],
                "messages": [],
                "sources": [],
                "user_feedback": "auto",
            })
            assert len(result["sources"]) == 1  # Deduplicated


class TestWriterNode:
    """Verify writer_node handles content filter and feedback."""

    def test_content_filter_error(self):
        """Content filter in writer returns error state, not crash."""
        from src.nodes import writer_node
        from openai import BadRequestError

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {}

        with patch("src.nodes.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.side_effect = BadRequestError(
                message="data_inspection_failed",
                response=mock_resp,
                body={"message": "data_inspection_failed", "code": "DataInspectionFailed"}
            )
            result = writer_node({
                "topic": "AI",
                "messages": [],
                "sources": [{"title": "Test", "url": "http://test.com", "snippet": "test"}],
                "research_steps": ["step 1"],
                "user_feedback": "",
            })
            assert "error_message" in result
            assert "CONTENT_FILTER" in result["error_message"]

    def test_user_feedback_injection(self):
        """Writer prompt includes user feedback when present."""
        from src.nodes import writer_node
        mock_response = MagicMock()
        mock_response.content = "# Report\n\nContent here."

        with patch("src.nodes.get_llm") as mock_get_llm:
            mock_llm = mock_get_llm.return_value
            mock_llm.invoke.return_value = mock_response

            writer_node({
                "topic": "AI",
                "messages": [],
                "sources": [],
                "research_steps": ["step 1"],
                "user_feedback": "modify: Add more technical details",
            })
            # Verify the prompt includes the feedback
            call_args = mock_llm.invoke.call_args
            prompt_text = call_args[0][0][0].content
            # Should contain the user's feedback text
            assert "Add more technical details" in prompt_text
