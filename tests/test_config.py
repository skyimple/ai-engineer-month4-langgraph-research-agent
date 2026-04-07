"""Tests for lazy initialization in config.py."""
import pytest
import os


class TestLazyConfig:
    """Verify config.py doesn't crash on import without API key."""

    def test_import_without_api_key(self, monkeypatch):
        """Importing config should not raise ValueError even without API key."""
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        # Force reimport
        import importlib
        import src.config
        importlib.reload(src.config)
        # Should NOT have raised on import

    def test_get_llm_raises_without_key(self, monkeypatch):
        """get_llm() should raise ValueError when API key is missing."""
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        import importlib
        import src.config
        importlib.reload(src.config)

        # Reset cached instance and ensure no key in env
        src.config._llm = None
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
            src.config.get_llm()

    def test_get_llm_returns_instance_with_key(self, monkeypatch):
        """get_llm() should return an LLM instance when key is set."""
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key-123")
        import importlib
        import src.config
        importlib.reload(src.config)

        # Reset cached instance
        src.config._llm = None

        llm = src.config.get_llm()
        assert llm is not None

    def test_get_llm_caches_instance(self, monkeypatch):
        """get_llm() should return the same instance on repeated calls."""
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key-123")
        import importlib
        import src.config
        importlib.reload(src.config)

        src.config._llm = None
        llm1 = src.config.get_llm()
        llm2 = src.config.get_llm()
        assert llm1 is llm2
