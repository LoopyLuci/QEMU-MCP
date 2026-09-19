"""Provider Store — encrypted API key storage and usage tracking."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet

logger = logging.getLogger("qemu-mcp.providers")

PROVIDER_STORE_DIR = Path.home() / ".local" / "share" / "qemu-mcp"
PROVIDER_STORE_FILE = PROVIDER_STORE_DIR / "providers.enc"
MASTER_KEY_FILE = PROVIDER_STORE_DIR / ".providers_key"


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""
    name: str  # "openrouter", "anthropic", "openai", "google"
    display_name: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60
    enabled: bool = True
    priority: int = 0  # Lower = higher priority for failover
    custom_headers: dict[str, str] = field(default_factory=dict)


@dataclass 
class UsageRecord:
    """Record of API usage."""
    timestamp: float
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    success: bool
    error: str = ""


class ProviderStore:
    """Encrypted storage for AI provider configurations and usage."""
    
    # Default provider configurations
    DEFAULT_PROVIDERS = {
        "openrouter": ProviderConfig(
            name="openrouter",
            base_url="https://openrouter.ai/api/v1",
            model="openai/gpt-4o-mini",
            priority=1,
        ),
        "anthropic": ProviderConfig(
            name="anthropic",
            base_url="https://api.anthropic.com",
            model="claude-sonnet-4-20250514",
            priority=2,
        ),
        "openai": ProviderConfig(
            name="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            priority=3,
        ),
        "google": ProviderConfig(
            name="google",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-2.0-flash",
            priority=4,
        ),
        "ollama": ProviderConfig(
            name="ollama",
            base_url="http://localhost:11434/v1",
            model="llama3.2",
            priority=0,  # Highest priority (local, free)
        ),
    }
    
    def __init__(self):
        self._providers: dict[str, ProviderConfig] = {}
        self._usage: list[UsageRecord] = []
        self._fernet: Optional[Fernet] = None
        self._ensure_store_dir()
        self._init_encryption()
        self._load()
    
    def _ensure_store_dir(self):
        """Ensure store directory exists."""
        PROVIDER_STORE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _init_encryption(self):
        """Initialize or load encryption key."""
        if MASTER_KEY_FILE.exists():
            key = MASTER_KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            MASTER_KEY_FILE.write_bytes(key)
            MASTER_KEY_FILE.chmod(0o600)
        self._fernet = Fernet(key)
    
    def _load(self):
        """Load encrypted provider configs from disk."""
        if PROVIDER_STORE_FILE.exists():
            try:
                encrypted = PROVIDER_STORE_FILE.read_bytes()
                decrypted = self._fernet.decrypt(encrypted)
                data = json.loads(decrypted)
                
                for name, config_data in data.get("providers", {}).items():
                    self._providers[name] = ProviderConfig(**config_data)
                
                for usage_data in data.get("usage", []):
                    self._usage.append(UsageRecord(**usage_data))
                
                logger.info("Loaded %d providers, %d usage records",
                           len(self._providers), len(self._usage))
            except Exception as e:
                logger.error("Failed to load provider store: %s", e)
                self._load_defaults()
        else:
            self._load_defaults()
    
    def _load_defaults(self):
        """Load default provider configurations."""
        self._providers = dict(self.DEFAULT_PROVIDERS)
        self._save()
    
    def _save(self):
        """Save encrypted provider configs to disk."""
        data = {
            "providers": {
                name: {
                    "name": p.name,
                    "api_key": p.api_key,
                    "base_url": p.base_url,
                    "model": p.model,
                    "max_tokens": p.max_tokens,
                    "temperature": p.temperature,
                    "timeout": p.timeout,
                    "enabled": p.enabled,
                    "priority": p.priority,
                    "custom_headers": p.custom_headers,
                }
                for name, p in self._providers.items()
            },
            "usage": [
                {
                    "timestamp": r.timestamp,
                    "provider": r.provider,
                    "model": r.model,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "total_tokens": r.total_tokens,
                    "cost_usd": r.cost_usd,
                    "latency_ms": r.latency_ms,
                    "success": r.success,
                    "error": r.error,
                }
                for r in self._usage[-1000:]  # Keep last 1000 records
            ],
        }
        
        decrypted = json.dumps(data).encode()
        encrypted = self._fernet.encrypt(decrypted)
        PROVIDER_STORE_FILE.write_bytes(encrypted)
        PROVIDER_STORE_FILE.chmod(0o600)
    
    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get a provider configuration."""
        return self._providers.get(name)
    
    def get_all_providers(self) -> dict[str, ProviderConfig]:
        """Get all provider configurations."""
        return dict(self._providers)
    
    def get_enabled_providers(self) -> list[ProviderConfig]:
        """Get enabled providers sorted by priority."""
        return sorted(
            [p for p in self._providers.values() if p.enabled and p.api_key],
            key=lambda p: p.priority,
        )
    
    def update_provider(self, name: str, **kwargs):
        """Update a provider configuration."""
        if name in self._providers:
            provider = self._providers[name]
            for key, value in kwargs.items():
                if hasattr(provider, key):
                    setattr(provider, key, value)
            self._save()
    
    def set_api_key(self, name: str, api_key: str):
        """Set API key for a provider."""
        if name in self._providers:
            self._providers[name].api_key = api_key
            self._save()
    
    def add_provider(self, config: ProviderConfig):
        """Add a custom provider."""
        self._providers[config.name] = config
        self._save()
    
    def remove_provider(self, name: str):
        """Remove a provider."""
        if name in self._providers:
            del self._providers[name]
            self._save()
    
    def record_usage(self, record: UsageRecord):
        """Record API usage."""
        self._usage.append(record)
        self._save()
    
    def get_usage_summary(self) -> dict[str, Any]:
        """Get usage summary statistics."""
        if not self._usage:
            return {"total_requests": 0, "total_cost": 0, "total_tokens": 0}
        
        return {
            "total_requests": len(self._usage),
            "total_cost": sum(r.cost_usd for r in self._usage),
            "total_tokens": sum(r.total_tokens for r in self._usage),
            "total_prompt_tokens": sum(r.prompt_tokens for r in self._usage),
            "total_completion_tokens": sum(r.completion_tokens for r in self._usage),
            "success_rate": sum(1 for r in self._usage if r.success) / len(self._usage),
            "avg_latency_ms": sum(r.latency_ms for r in self._usage) / len(self._usage),
            "by_provider": {
                name: {
                    "requests": len([r for r in self._usage if r.provider == name]),
                    "cost": sum(r.cost_usd for r in self._usage if r.provider == name),
                    "tokens": sum(r.total_tokens for r in self._usage if r.provider == name),
                }
                for name in set(r.provider for r in self._usage)
            },
        }
    
    def get_recent_usage(self, limit: int = 50) -> list[UsageRecord]:
        """Get recent usage records."""
        return self._usage[-limit:]
