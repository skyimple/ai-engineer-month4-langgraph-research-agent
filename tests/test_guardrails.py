"""Tests for guardrails — integration of _check_patterns with real inputs."""
import pytest
from src.guardrails.rails import _check_patterns, check_input_guardrails, check_output_guardrails


class TestInputGuardrails:
    """Verify input guardrails block dangerous patterns."""

    def test_sql_injection_blocked(self):
        assert not _check_patterns("DROP TABLE users")[0]
        assert not _check_patterns("UNION SELECT * FROM users")[0]
        assert not _check_patterns("1 OR 1=1")[0]

    def test_code_execution_blocked(self):
        assert not _check_patterns("eval('malicious')")[0]
        assert not _check_patterns("__import__('os')")[0]

    def test_xss_blocked(self):
        assert not _check_patterns('<script>alert(1)</script>')[0]
        assert not _check_patterns('javascript:alert(1)')[0]

    def test_path_traversal_blocked(self):
        assert not _check_patterns("../../etc/passwd")[0]

    def test_normal_research_topic_passes(self):
        """Legitimate research topics should NOT be blocked."""
        is_safe, msg = _check_patterns("人工智能的最新发展趋势")
        assert is_safe, f"False positive: {msg}"

    def test_topic_with_dollar_sign_passes(self):
        """Research topics containing $ for currency should pass after fix."""
        is_safe, msg = _check_patterns("AI market size exceeds $100 billion")
        assert is_safe, f"False positive on dollar sign: {msg}"

    def test_topic_with_semicolon_passes(self):
        """Topics with semicolons (e.g., list separators) should pass."""
        is_safe, msg = _check_patterns("AI; machine learning; deep learning trends")
        assert is_safe, f"False positive on semicolon: {msg}"

    def test_topic_with_comparison_passes(self):
        """Topics with comparison operators should pass."""
        is_safe, msg = _check_patterns("Revenue growth > 50% this year")
        assert is_safe, f"False positive on comparison: {msg}"

    def test_empty_input_blocked(self):
        is_safe, _ = check_input_guardrails("")
        assert not is_safe

    def test_whitespace_input_blocked(self):
        is_safe, _ = check_input_guardrails("   ")
        assert not is_safe


class TestOutputGuardrails:
    """Verify output guardrails check generated content."""

    def test_safe_output_passes(self):
        is_safe, _ = check_output_guardrails("这是一份关于AI的研究报告。")
        assert is_safe

    def test_empty_output_blocked(self):
        is_safe, _ = check_output_guardrails("")
        assert not is_safe

    def test_dangerous_output_blocked(self):
        is_safe, _ = check_output_guardrails('<script>alert("xss")</script>')
        assert not is_safe
