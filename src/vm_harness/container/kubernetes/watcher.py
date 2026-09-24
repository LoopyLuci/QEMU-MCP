"""Kubernetes event watcher.

Provides real-time watch functionality for Kubernetes resources
using the official kubernetes-client watch API, emitting typed events
as they occur.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from kubernetes import watch
from kubernetes.client.exceptions import ApiException

from vm_harness.container.kubernetes.models import (
    Deployment,
    Ingress,
    KubeService,
    Namespace,
    Pod,
)

logger = logging.getLogger(__name__)


# ── Event Types ────────────────────────────────────────────────────────────────

class EventType(str, Enum):
    """Kubernetes watch event types."""
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    ERROR = "ERROR"
    BOOKMARK = "BOOKMARK"


class WatchEvent:
    """Represents a Kubernetes watch event.

    Attributes:
        type: Event type (ADDED, MODIFIED, DELETED, ERROR).
        resource_type: Resource class (Pod, Deployment, etc.).
        resource_name: Name of the affected resource.
        namespace: Namespace of the resource (if applicable).
        resource: The full resource object (when available).
    """

    def __init__(
        self,
        event_type: EventType,
        resource_type: str,
        resource_name: str,
        namespace: Optional[str] = None,
        resource: Optional[Any] = None,
    ):
        self.type = event_type
        self.resource_type = resource_type
        self.resource_name = resource_name
        self.namespace = namespace
        self.resource = resource

    def __repr__(self) -> str:
        return (
            f"WatchEvent(type={self.type.value!r}, "
            f"resource={self.resource_type!r}/{self.resource_name!r})"
        )


# ── Kubernetes Watcher ─────────────────────────────────────────────────────────

class KubernetesWatcher:
    """Watch Kubernetes resources for real-time events.

    Uses the kubernetes-client watch API to stream events for pods,
    deployments, services, ingresses, and namespaces.
    """

    def __init__(self, core_v1, apps_v1, networking_v1):
        """
        Args:
            core_v1: CoreV1Api instance.
            apps_v1: AppsV1Api instance.
            networking_v1: NetworkingV1Api instance.
        """
        self._core = core_v1
        self._apps = apps_v1
        self._networking = networking_v1
        self._active_watches: Dict[str, asyncio.Task] = {}

    async def watch_pods(
        self,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None,
        field_selector: Optional[str] = None,
    ) -> AsyncIterator[WatchEvent]:
        """Watch pods for changes.

        Args:
            namespace: Namespace to watch (None for all).
            label_selector: Label filter.
            field_selector: Field filter.

        Yields:
            WatchEvent objects as changes occur.
        """
        loop = asyncio.get_event_loop()

        def _watch():
            w = watch.Watch()
            kwargs: Dict[str, Any] = {}
            if label_selector:
                kwargs["label_selector"] = label_selector
            if field_selector:
                kwargs["field_selector"] = field_selector

            try:
                if namespace:
                    return w.stream(
                        self._core.list_namespaced_pod,
                        namespace=namespace,
                        **kwargs,
                    )
                else:
                    return w.stream(self._core.list_pod_for_all_namespaces, **kwargs)
            except ApiException as e:
                logger.error(f"Watch error for pods: {e}")
                raise

        # Run the blocking watch in executor
        event_stream = await loop.run_in_executor(None, _watch)

        try:
            for event in event_stream:
                yield self._parse_pod_event(event)
        except Exception as e:
            logger.error(f"Pod watch stream error: {e}")
            raise

    async def watch_deployments(
        self,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None,
    ) -> AsyncIterator[WatchEvent]:
        """Watch deployments for changes.

        Args:
            namespace: Namespace to watch (None for all).
            label_selector: Label filter.

        Yields:
            WatchEvent objects.
        """
        loop = asyncio.get_event_loop()

        def _watch():
            w = watch.Watch()
            kwargs: Dict[str, Any] = {}
            if label_selector:
                kwargs["label_selector"] = label_selector

            try:
                if namespace:
                    return w.stream(
                        self._apps.list_namespaced_deployment,
                        namespace=namespace,
                        **kwargs,
                    )
                else:
                    return w.stream(
                        self._apps.list_deployment_for_all_namespaces,
                        **kwargs,
                    )
            except ApiException as e:
                logger.error(f"Watch error for deployments: {e}")
                raise

        event_stream = await loop.run_in_executor(None, _watch)

        try:
            for event in event_stream:
                yield self._parse_deployment_event(event)
        except Exception as e:
            logger.error(f"Deployment watch stream error: {e}")
            raise

    async def watch_services(
        self,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None,
    ) -> AsyncIterator[WatchEvent]:
        """Watch services for changes.

        Args:
            namespace: Namespace to watch (None for all).
            label_selector: Label filter.

        Yields:
            WatchEvent objects.
        """
        loop = asyncio.get_event_loop()

        def _watch():
            w = watch.Watch()
            kwargs: Dict[str, Any] = {}
            if label_selector:
                kwargs["label_selector"] = label_selector

            try:
                if namespace:
                    return w.stream(
                        self._core.list_namespaced_service,
                        namespace=namespace,
                        **kwargs,
                    )
                else:
                    return w.stream(
                        self._core.list_service_for_all_namespaces,
                        **kwargs,
                    )
            except ApiException as e:
                logger.error(f"Watch error for services: {e}")
                raise

        event_stream = await loop.run_in_executor(None, _watch)

        try:
            for event in event_stream:
                yield self._parse_service_event(event)
        except Exception as e:
            logger.error(f"Service watch stream error: {e}")
            raise

    async def watch_ingresses(
        self,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None,
    ) -> AsyncIterator[WatchEvent]:
        """Watch ingresses for changes.

        Args:
            namespace: Namespace to watch (None for all).
            label_selector: Label filter.

        Yields:
            WatchEvent objects.
        """
        loop = asyncio.get_event_loop()

        def _watch():
            w = watch.Watch()
            kwargs: Dict[str, Any] = {}
            if label_selector:
                kwargs["label_selector"] = label_selector

            try:
                if namespace:
                    return w.stream(
                        self._networking.list_namespaced_ingress,
                        namespace=namespace,
                        **kwargs,
                    )
                else:
                    return w.stream(
                        self._networking.list_ingress_for_all_namespaces,
                        **kwargs,
                    )
            except ApiException as e:
                logger.error(f"Watch error for ingresses: {e}")
                raise

        event_stream = await loop.run_in_executor(None, _watch)

        try:
            for event in event_stream:
                yield self._parse_ingress_event(event)
        except Exception as e:
            logger.error(f"Ingress watch stream error: {e}")
            raise

    async def watch_namespaces(
        self,
        label_selector: Optional[str] = None,
    ) -> AsyncIterator[WatchEvent]:
        """Watch namespaces for changes.

        Args:
            label_selector: Label filter.

        Yields:
            WatchEvent objects.
        """
        loop = asyncio.get_event_loop()

        def _watch():
            w = watch.Watch()
            kwargs: Dict[str, Any] = {}
            if label_selector:
                kwargs["label_selector"] = label_selector

            try:
                return w.stream(self._core.list_namespace, **kwargs)
            except ApiException as e:
                logger.error(f"Watch error for namespaces: {e}")
                raise

        event_stream = await loop.run_in_executor(None, _watch)

        try:
            for event in event_stream:
                yield self._parse_namespace_event(event)
        except Exception as e:
            logger.error(f"Namespace watch stream error: {e}")
            raise

    async def watch_events(
        self,
        namespace: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Watch cluster events.

        Args:
            namespace: Namespace to watch (None for all).

        Yields:
            Raw event dicts.
        """
        loop = asyncio.get_event_loop()

        def _watch():
            w = watch.Watch()
            try:
                if namespace:
                    return w.stream(
                        self._core.list_namespaced_event,
                        namespace=namespace,
                    )
                else:
                    return w.stream(self._core.list_event_for_all_namespaces)
            except ApiException as e:
                logger.error(f"Watch error for events: {e}")
                raise

        event_stream = await loop.run_in_executor(None, _watch)

        try:
            for event in event_stream:
                obj = event["object"]
                yield {
                    "type": event["type"],
                    "reason": obj.reason,
                    "message": obj.message,
                    "source": str(obj.source),
                    "involved_object": {
                        "kind": obj.involved_object.kind,
                        "name": obj.involved_object.name,
                        "namespace": obj.involved_object.namespace,
                    },
                    "timestamp": obj.last_timestamp,
                }
        except Exception as e:
            logger.error(f"Cluster event watch stream error: {e}")
            raise

    # ── Managed Watch Tasks ────────────────────────────────────────────────────

    async def start_watch(
        self,
        watch_id: str,
        resource_type: str,
        callback: Callable[[WatchEvent], None],
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None,
    ) -> None:
        """Start a managed watch task.

        Args:
            watch_id: Unique identifier for this watch.
            resource_type: Type of resource (pods, deployments, etc.).
            callback: Function to call on each event.
            namespace: Namespace to watch.
            label_selector: Label filter.
        """
        if watch_id in self._active_watches:
            raise ValueError(f"Watch '{watch_id}' is already running")

        task = asyncio.create_task(
            self._run_watch(watch_id, resource_type, callback, namespace, label_selector)
        )
        self._active_watches[watch_id] = task

    async def stop_watch(self, watch_id: str) -> None:
        """Stop a managed watch task.

        Args:
            watch_id: Watch identifier.
        """
        task = self._active_watches.pop(watch_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def stop_all(self) -> None:
        """Stop all managed watch tasks."""
        for watch_id in list(self._active_watches.keys()):
            await self.stop_watch(watch_id)

    async def _run_watch(
        self,
        watch_id: str,
        resource_type: str,
        callback: Callable[[WatchEvent], None],
        namespace: Optional[str],
        label_selector: Optional[str],
    ) -> None:
        """Internal watch runner for managed tasks."""
        watch_methods = {
            "pods": self.watch_pods,
            "deployments": self.watch_deployments,
            "services": self.watch_services,
            "ingresses": self.watch_ingresses,
            "namespaces": self.watch_namespaces,
        }

        method = watch_methods.get(resource_type)
        if not method:
            raise ValueError(f"Unknown resource type: {resource_type}")

        try:
            async for event in method(
                namespace=namespace,
                label_selector=label_selector,
            ):
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Watch callback error for {watch_id}: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Watch task error for {watch_id}: {e}")
        finally:
            self._active_watches.pop(watch_id, None)

    # ── Event Parsers ───────────────────────────────────────────────────────────

    def _parse_pod_event(self, event: Dict[str, Any]) -> WatchEvent:
        """Parse a pod watch event."""
        obj = event["object"]
        metadata = obj.metadata
        pod = Pod.from_dict(obj.to_dict()) if hasattr(obj, "to_dict") else None

        return WatchEvent(
            event_type=EventType(event["type"]),
            resource_type="Pod",
            resource_name=metadata.name,
            namespace=metadata.namespace,
            resource=pod,
        )

    def _parse_deployment_event(self, event: Dict[str, Any]) -> WatchEvent:
        """Parse a deployment watch event."""
        obj = event["object"]
        metadata = obj.metadata
        deployment = Deployment.from_dict(obj.to_dict()) if hasattr(obj, "to_dict") else None

        return WatchEvent(
            event_type=EventType(event["type"]),
            resource_type="Deployment",
            resource_name=metadata.name,
            namespace=metadata.namespace,
            resource=deployment,
        )

    def _parse_service_event(self, event: Dict[str, Any]) -> WatchEvent:
        """Parse a service watch event."""
        obj = event["object"]
        metadata = obj.metadata
        service = KubeService.from_dict(obj.to_dict()) if hasattr(obj, "to_dict") else None

        return WatchEvent(
            event_type=EventType(event["type"]),
            resource_type="Service",
            resource_name=metadata.name,
            namespace=metadata.namespace,
            resource=service,
        )

    def _parse_ingress_event(self, event: Dict[str, Any]) -> WatchEvent:
        """Parse an ingress watch event."""
        obj = event["object"]
        metadata = obj.metadata
        ingress = Ingress.from_dict(obj.to_dict()) if hasattr(obj, "to_dict") else None

        return WatchEvent(
            event_type=EventType(event["type"]),
            resource_type="Ingress",
            resource_name=metadata.name,
            namespace=metadata.namespace,
            resource=ingress,
        )

    def _parse_namespace_event(self, event: Dict[str, Any]) -> WatchEvent:
        """Parse a namespace watch event."""
        obj = event["object"]
        metadata = obj.metadata
        ns = Namespace.from_dict(obj.to_dict()) if hasattr(obj, "to_dict") else None

        return WatchEvent(
            event_type=EventType(event["type"]),
            resource_type="Namespace",
            resource_name=metadata.name,
            resource=ns,
        )
