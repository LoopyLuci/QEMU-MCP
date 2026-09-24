"""Low-level Docker API wrapper.

Provides a thin async wrapper around docker-py for direct API calls
that are not covered by the high-level DockerBackend interface.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from docker import DockerClient
from docker.errors import DockerException


class DockerAPIError(Exception):
    """Docker API error."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause


class DockerAPI:
    """Low-level Docker API wrapper."""

    def __init__(self, client: DockerClient):
        self._client = client

    async def _run(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def ping(self) -> bool:
        """Check if Docker daemon is reachable."""
        try:
            return await self._run(self._client.ping)
        except DockerException as e:
            raise DockerAPIError(f"Ping failed: {e}", e)

    async def version(self) -> Dict[str, Any]:
        """Get Docker daemon version info."""
        try:
            return await self._run(self._client.version)
        except DockerException as e:
            raise DockerAPIError(f"Failed to get version: {e}", e)

    async def info(self) -> Dict[str, Any]:
        """Get Docker daemon system info."""
        try:
            return await self._run(self._client.info)
        except DockerException as e:
            raise DockerAPIError(f"Failed to get info: {e}", e)

    async def events(self, since: Optional[str] = None, until: Optional[str] = None):
        """Stream Docker events."""
        kwargs: Dict[str, Any] = {}
        if since:
            kwargs["since"] = since
        if until:
            kwargs["until"] = until
        try:
            return await self._run(self._client.events, **kwargs)
        except DockerException as e:
            raise DockerAPIError(f"Failed to get events: {e}", e)

    async def prune_containers(self, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Remove stopped containers."""
        try:
            return await self._run(self._client.containers.prune, filters=filters or {})
        except DockerException as e:
            raise DockerAPIError(f"Failed to prune containers: {e}", e)

    async def prune_images(self, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Remove unused images."""
        try:
            return await self._run(self._client.images.prune, filters=filters or {})
        except DockerException as e:
            raise DockerAPIError(f"Failed to prune images: {e}", e)

    async def prune_volumes(self, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Remove unused volumes."""
        try:
            return await self._run(self._client.volumes.prune, filters=filters or {})
        except DockerException as e:
            raise DockerAPIError(f"Failed to prune volumes: {e}", e)

    async def prune_networks(self, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Remove unused networks."""
        try:
            return await self._run(self._client.networks.prune, filters=filters or {})
        except DockerException as e:
            raise DockerAPIError(f"Failed to prune networks: {e}", e)
