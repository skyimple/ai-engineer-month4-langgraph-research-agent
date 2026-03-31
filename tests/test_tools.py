"""Tests for the search tool — structured data return and formatting."""
from src.tools import search_tool, format_search_results, calculator_tool


class TestSearchToolStructure:
    """Verify search_tool returns structured list of dicts."""

    def test_format_empty_results(self):
        assert format_search_results([]) == "No results found."

    def test_format_single_result(self):
        results = [{"title": "Test", "href": "https://test.com", "body": "test body"}]
        formatted = format_search_results(results)
        assert "Test" in formatted
        assert "https://test.com" in formatted
        assert "test body" in formatted

    def test_format_multiple_results(self):
        results = [
            {"title": "A", "href": "https://a.com", "body": "body a"},
            {"title": "B", "href": "https://b.com", "body": "body b"},
        ]
        formatted = format_search_results(results)
        assert "- A: https://a.com" in formatted
        assert "- B: https://b.com" in formatted


class TestCalculatorTool:
    """Verify calculator safety — AST-based eval, no code execution."""

    def test_basic_arithmetic(self):
        result = calculator_tool.invoke("2 + 2")
        assert result == "4"

    def test_multiplication(self):
        result = calculator_tool.invoke("10 * 5")
        assert result == "50"

    def test_power(self):
        result = calculator_tool.invoke("2 ** 10")
        assert result == "1024"

    def test_negative_number(self):
        result = calculator_tool.invoke("-5")
        assert result == "-5"

    def test_division(self):
        result = calculator_tool.invoke("10 / 3")
        assert "3.333" in result

    def test_rejects_invalid_chars(self):
        """Letters and dangerous chars should be rejected."""
        result = calculator_tool.invoke("import os")
        assert "Error" in result or "Invalid characters" in result

    def test_rejects_function_call(self):
        """AST-based eval should NOT allow function calls."""
        result = calculator_tool.invoke("print('hello')")
        assert "Error" in result or "Invalid" in result or "Unsupported" in result

    def test_empty_expression(self):
        result = calculator_tool.invoke("")
        assert "Error" in result or "Calculation error" in result
