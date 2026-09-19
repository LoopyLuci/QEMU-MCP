"""Comprehensive tests for AI Provider System and Agentic Chat."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "src"))

import gui.provider_store as _ps_module
from gui.api_providers import APIProviders, APIResponse
from gui.chat_engine import ChatEngine, ChatMessage


# ── Provider Store Tests ─────────────────────────────────────────────────────


class TestProviderStore:
    """Test suite for ProviderStore — encrypted API key storage."""

    def setup_method(self):
        """Create a temporary store for each test."""
        self.tmp_dir = tempfile.mkdtemp()
        # Patch module-level paths BEFORE creating ProviderStore
        _ps_module.PROVIDER_STORE_FILE = Path(self.tmp_dir) / "providers.enc"
        _ps_module.MASTER_KEY_FILE = Path(self.tmp_dir) / ".providers_key"
        from gui.provider_store import ProviderConfig, ProviderStore, UsageRecord
        self.ProviderConfig = ProviderConfig
        self.ProviderStore = ProviderStore
        self.UsageRecord = UsageRecord
        self.store = ProviderStore()

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_store_initializes_with_defaults(self):
        """Store initializes with default providers."""
        providers = self.store.get_all_providers()
        assert len(providers) > 0
        assert "openrouter" in providers or "ollama" in providers

    def test_encrypt_decrypt_api_key(self):
        """API key encryption and decryption works."""
        from cryptography.fernet import Fernet
        fernet = Fernet(Fernet.generate_key())
        original = "sk-test-key-12345"
        encrypted = fernet.encrypt(original.encode())
        decrypted = fernet.decrypt(encrypted).decode()
        assert decrypted == original

    def test_set_api_key(self):
        """Setting an API key updates the provider."""
        self.store.set_api_key("openrouter", "sk-test-123")
        provider = self.store.get_provider("openrouter")
        assert provider is not None
        assert provider.api_key == "sk-test-123"

    def test_get_enabled_providers(self):
        """Only enabled providers with API keys are returned."""
        # No keys set initially
        enabled = self.store.get_enabled_providers()
        assert isinstance(enabled, list)
        # Set a key
        self.store.set_api_key("openrouter", "sk-test-123")
        enabled = self.store.get_enabled_providers()
        assert any(p.name == "openrouter" for p in enabled)

    def test_add_provider(self):
        """Adding a custom provider works."""
        config = self.ProviderConfig(
            name="custom-llm",
            display_name="Custom LLM",
            base_url="https://api.custom.com/v1",
            api_key="custom-key",
            model="custom-model",
        )
        self.store.add_provider(config)
        assert "custom-llm" in self.store.get_all_providers()

    def test_remove_provider(self):
        """Removing a provider works."""
        providers = self.store.get_all_providers()
        name = list(providers.keys())[0]
        self.store.remove_provider(name)
        assert name not in self.store.get_all_providers()

    def test_record_usage(self):
        """Usage recording works."""
        record = self.UsageRecord(
            timestamp=1000.0,
            provider="openrouter",
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            latency_ms=500.0,
            success=True,
        )
        self.store.record_usage(record)
        recent = self.store.get_recent_usage(limit=1)
        assert len(recent) == 1
        assert recent[0].provider == "openrouter"

    def test_get_usage_summary(self):
        """Usage summary is correctly aggregated."""
        for i in range(3):
            self.store.record_usage(self.UsageRecord(
                timestamp=float(i),
                provider="openrouter",
                model="test-model",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=0.001,
                latency_ms=500.0,
                success=True,
            ))
        summary = self.store.get_usage_summary()
        assert summary["total_requests"] == 3
        assert "openrouter" in summary["by_provider"]
        assert summary["by_provider"]["openrouter"]["requests"] == 3

    def test_persistence(self):
        """Store data persists to disk."""
        self.store.set_api_key("openrouter", "sk-persist-test")
        self.store._save()

        # Create new store pointing to same file
        store2 = self.ProviderStore()
        provider = store2.get_provider("openrouter")
        assert provider is not None
        assert provider.api_key == "sk-persist-test"


# ── API Providers Tests ─────────────────────────────────────────────────────


class TestAPIProviders:
    """Test suite for APIProviders — LLM API calls with failover."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tmp_dir = tempfile.mkdtemp()
        _ps_module.PROVIDER_STORE_FILE = Path(self.tmp_dir) / "providers.enc"
        _ps_module.MASTER_KEY_FILE = Path(self.tmp_dir) / ".providers_key"
        from gui.provider_store import ProviderStore
        self.store = ProviderStore()
        self.providers = APIProviders(self.store)

    def teardown_method(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_estimate_cost(self):
        """Cost estimation is correct."""
        cost = self.providers._estimate_cost("openai", "gpt-4o", 1000, 500)
        assert cost > 0
        expected = 1000 * 2.50 / 1_000_000 + 500 * 10.00 / 1_000_000
        assert abs(cost - expected) < 0.001

    def test_no_providers_returns_error(self):
        """No providers configured returns error response."""
        self.store._providers.clear()
        asyncio.run(self._test_no_providers())

    async def _test_no_providers(self):
        response = await self.providers.call([{"role": "user", "content": "test"}])
        assert not response.success
        assert "No API providers configured" in response.error


# ── Chat Engine Tests ───────────────────────────────────────────────────────


class TestChatEngine:
    """Test suite for ChatEngine — agentic LLM chat."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tmp_dir = tempfile.mkdtemp()
        _ps_module.PROVIDER_STORE_FILE = Path(self.tmp_dir) / "providers.enc"
        _ps_module.MASTER_KEY_FILE = Path(self.tmp_dir) / ".providers_key"
        from gui.provider_store import ProviderStore
        self.store = ProviderStore()
        self.providers = APIProviders(self.store)
        self.engine = ChatEngine(self.providers)

    def teardown_method(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_chat_message_creation(self):
        """ChatMessage is correctly created."""
        msg = ChatMessage("user", "Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.tool_name == ""

    def test_add_message(self):
        """Adding messages to history works."""
        msg = ChatMessage("user", "Test")
        self.engine.add_message(msg)
        assert len(self.engine._history) == 1

    def test_clear_history(self):
        """Clearing history works."""
        self.engine.add_message(ChatMessage("user", "Test"))
        self.engine.clear_history()
        assert len(self.engine._history) == 0

    def test_tools_defined(self):
        """ChatEngine has QEMU tools defined."""
        assert hasattr(self.engine, "TOOLS")
        assert len(self.engine.TOOLS) > 0
        tool_names = [t["function"]["name"] for t in self.engine.TOOLS]
        assert "vm_status" in tool_names

    def test_tool_schema_valid(self):
        """Each tool has a valid JSON schema."""
        for tool in self.engine.TOOLS:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]


# ── Chat Message Tests ──────────────────────────────────────────────────────


class TestChatMessage:
    """Test ChatMessage data class."""

    def test_to_dict(self):
        """to_dict() returns correct format."""
        msg = ChatMessage("user", "Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_with_tool_info(self):
        """Message with tool info works."""
        msg = ChatMessage("assistant", "", tool_name="vm_status")
        assert msg.tool_name == "vm_status"

    def test_with_tool_args(self):
        """Message with tool args works."""
        msg = ChatMessage("tool", "Result", tool_name="vm_status", tool_args={"vm": "test"})
        assert msg.tool_args == {"vm": "test"}


# ── Integration Tests ───────────────────────────────────────────────────────


class TestProviderIntegration:
    """Integration tests for provider system."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.tmp_dir = tempfile.mkdtemp()
        _ps_module.PROVIDER_STORE_FILE = Path(self.tmp_dir) / "providers.enc"
        _ps_module.MASTER_KEY_FILE = Path(self.tmp_dir) / ".providers_key"
        from gui.provider_store import ProviderConfig, ProviderStore, UsageRecord
        self.ProviderConfig = ProviderConfig
        self.ProviderStore = ProviderStore
        self.UsageRecord = UsageRecord

    def teardown_method(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_full_provider_lifecycle(self):
        """Test complete provider lifecycle."""
        store = self.ProviderStore()

        # Add provider
        config = self.ProviderConfig(
            name="test-provider",
            display_name="Test",
            base_url="https://api.test.com/v1",
            api_key="test-key",
            model="test-model",
        )
        store.add_provider(config)

        # Set key
        store.set_api_key("test-provider", "sk-new-key")

        # Enable
        store.update_provider("test-provider", enabled=True)

        # Verify
        enabled = store.get_enabled_providers()
        assert any(p.name == "test-provider" for p in enabled)

        # Record usage
        store.record_usage(self.UsageRecord(
            timestamp=1.0,
            provider="test-provider",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_usd=0.001,
            latency_ms=100.0,
            success=True,
        ))

        # Check summary
        summary = store.get_usage_summary()
        assert summary["by_provider"]["test-provider"]["requests"] == 1

        # Remove
        store.remove_provider("test-provider")
        assert "test-provider" not in store.get_all_providers()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
