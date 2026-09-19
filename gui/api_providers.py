"""API Providers — LLM API calls with automatic failover and usage tracking."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Optional

import aiohttp

from gui.provider_store import ProviderConfig, ProviderStore, UsageRecord

logger = logging.getLogger("qemu-mcp.api_providers")


class APIResponse:
    """Response from an LLM API call."""
    
    def __init__(
        self,
        content: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
        latency_ms: float = 0.0,
        provider: str = "",
        model: str = "",
        success: bool = True,
        error: str = "",
    ):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.provider = provider
        self.model = model
        self.success = success
        self.error = error


class APIProviders:
    """Manage LLM API calls with automatic failover and usage tracking."""
    
    # Cost per 1M tokens (approximate)
    COST_PER_1M_TOKENS = {
        "openrouter": {"default": 0.50},
        "anthropic": {
            "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
            "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
            "claude-haiku-4-20250514": {"input": 0.80, "output": 4.00},
        },
        "openai": {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
        },
        "google": {
            "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        },
        "ollama": {"default": 0.0},
    }
    
    def __init__(self, store: Optional[ProviderStore] = None):
        self._store = store or ProviderStore()
    
    def _estimate_cost(self, provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD for a request."""
        provider_costs = self.COST_PER_1M_TOKENS.get(provider, {})
        if "default" in provider_costs:
            rate = provider_costs["default"]
            return (prompt_tokens + completion_tokens) * rate / 1_000_000
        
        model_costs = provider_costs.get(model, {})
        if not model_costs:
            return 0.0
        
        input_cost = prompt_tokens * model_costs.get("input", 0) / 1_000_000
        output_cost = completion_tokens * model_costs.get("output", 0) / 1_000_000
        return input_cost + output_cost
    
    async def _call_openai_compatible(
        self,
        provider: ProviderConfig,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
    ) -> APIResponse:
        """Call an OpenAI-compatible API."""
        url = f"{provider.base_url}/chat/completions"
        
        payload = {
            "model": provider.model,
            "messages": messages,
            "max_tokens": provider.max_tokens,
            "temperature": provider.temperature,
        }
        
        if tools:
            payload["tools"] = tools
        
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(provider.custom_headers)
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=provider.timeout)) as resp:
                latency_ms = (time.time() - start_time) * 1000
                
                if resp.status != 200:
                    error_text = await resp.text()
                    return APIResponse(
                        content="",
                        latency_ms=latency_ms,
                        provider=provider.name,
                        model=provider.model,
                        success=False,
                        error=f"HTTP {resp.status}: {error_text[:200]}",
                    )
                
                data = await resp.json()
                
                # Extract token usage
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                
                # Extract content
                choices = data.get("choices", [])
                content = ""
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    
                    # Check for tool calls
                    tool_calls = message.get("tool_calls", [])
                    if tool_calls:
                        content = json.dumps({"tool_calls": tool_calls})
                
                cost = self._estimate_cost(provider.name, provider.model, prompt_tokens, completion_tokens)
                
                return APIResponse(
                    content=content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    provider=provider.name,
                    model=provider.model,
                    success=True,
                )
    
    async def _call_anthropic(
        self,
        provider: ProviderConfig,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
    ) -> APIResponse:
        """Call Anthropic API."""
        url = f"{provider.base_url}/v1/messages"
        
        # Convert OpenAI format to Anthropic format
        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append(msg)
        
        payload = {
            "model": provider.model,
            "messages": anthropic_messages,
            "max_tokens": provider.max_tokens,
            "temperature": provider.temperature,
        }
        
        if system_msg:
            payload["system"] = system_msg
        
        if tools:
            payload["tools"] = tools
        
        headers = {
            "x-api-key": provider.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        headers.update(provider.custom_headers)
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=provider.timeout)) as resp:
                latency_ms = (time.time() - start_time) * 1000
                
                if resp.status != 200:
                    error_text = await resp.text()
                    return APIResponse(
                        content="",
                        latency_ms=latency_ms,
                        provider=provider.name,
                        model=provider.model,
                        success=False,
                        error=f"HTTP {resp.status}: {error_text[:200]}",
                    )
                
                data = await resp.json()
                
                # Extract usage
                usage = data.get("usage", {})
                prompt_tokens = usage.get("input_tokens", 0)
                completion_tokens = usage.get("output_tokens", 0)
                total_tokens = prompt_tokens + completion_tokens
                
                # Extract content
                content_blocks = data.get("content", [])
                content = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        content += block.get("text", "")
                
                cost = self._estimate_cost(provider.name, provider.model, prompt_tokens, completion_tokens)
                
                return APIResponse(
                    content=content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    provider=provider.name,
                    model=provider.model,
                    success=True,
                )
    
    async def call(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        preferred_provider: str | None = None,
    ) -> APIResponse:
        """Call LLM API with automatic failover."""
        providers = self._store.get_enabled_providers()
        
        if not providers:
            return APIResponse(
                content="",
                success=False,
                error="No API providers configured. Please add an API key in Settings > AI Providers.",
            )
        
        # If preferred provider specified, try it first
        if preferred_provider:
            preferred = [p for p in providers if p.name == preferred_provider]
            if preferred:
                providers = preferred + [p for p in providers if p.name != preferred_provider]
        
        last_error = ""
        for provider in providers:
            try:
                if provider.name == "anthropic":
                    response = await self._call_anthropic(provider, messages, tools)
                else:
                    response = await self._call_openai_compatible(provider, messages, tools)
                
                # Record usage
                self._store.record_usage(UsageRecord(
                    timestamp=time.time(),
                    provider=response.provider,
                    model=response.model,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    total_tokens=response.total_tokens,
                    cost_usd=response.cost_usd,
                    latency_ms=response.latency_ms,
                    success=response.success,
                    error=response.error,
                ))
                
                if response.success:
                    return response
                
                last_error = response.error
                logger.warning("Provider %s failed: %s, trying next...", provider.name, last_error)
                
            except Exception as e:
                last_error = str(e)
                logger.error("Provider %s error: %s", provider.name, e)
                
                self._store.record_usage(UsageRecord(
                    timestamp=time.time(),
                    provider=provider.name,
                    model=provider.model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    cost_usd=0.0,
                    latency_ms=0.0,
                    success=False,
                    error=str(e),
                ))
        
        return APIResponse(
            content="",
            success=False,
            error=f"All providers failed. Last error: {last_error}",
        )
    
    async def stream_call(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        preferred_provider: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Call LLM API with streaming response."""
        providers = self._store.get_enabled_providers()
        
        if not providers:
            yield "Error: No API providers configured."
            return
        
        if preferred_provider:
            preferred = [p for p in providers if p.name == preferred_provider]
            if preferred:
                providers = preferred + [p for p in providers if p.name != preferred_provider]
        
        for provider in providers:
            try:
                url = f"{provider.base_url}/chat/completions"
                
                payload = {
                    "model": provider.model,
                    "messages": messages,
                    "max_tokens": provider.max_tokens,
                    "temperature": provider.temperature,
                    "stream": True,
                }
                
                if tools:
                    payload["tools"] = tools
                
                headers = {
                    "Authorization": f"Bearer {provider.api_key}",
                    "Content-Type": "application/json",
                }
                headers.update(provider.custom_headers)
                
                start_time = time.time()
                prompt_tokens = 0
                completion_tokens = 0
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=provider.timeout)) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.warning("Provider %s failed: %s", provider.name, error_text)
                            continue
                        
                        async for line in resp.content:
                            line = line.decode("utf-8").strip()
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                    choices = chunk.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                    
                                    usage = chunk.get("usage")
                                    if usage:
                                        prompt_tokens = usage.get("prompt_tokens", 0)
                                        completion_tokens = usage.get("completion_tokens", 0)
                                except json.JSONDecodeError:
                                    continue
                        
                        latency_ms = (time.time() - start_time) * 1000
                        total_tokens = prompt_tokens + completion_tokens
                        cost = self._estimate_cost(provider.name, provider.model, prompt_tokens, completion_tokens)
                        
                        self._store.record_usage(UsageRecord(
                            timestamp=time.time(),
                            provider=provider.name,
                            model=provider.model,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            cost_usd=cost,
                            latency_ms=latency_ms,
                            success=True,
                        ))
                        
                        return
            
            except Exception as e:
                logger.error("Provider %s streaming error: %s", provider.name, e)
                continue
        
        yield "Error: All providers failed."
