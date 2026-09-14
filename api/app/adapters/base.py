"""Common VMS adapter interface + registry.

A VMSAdapter is constructed from a `vms_systems` row and exposes a uniform
surface (health / list_cameras / poll_events) regardless of the underlying
vendor protocol. `get_adapter()` resolves the right class from adapter_type,
which is the extension point: register a new class to onboard a new vendor.
"""
from __future__ import annotations

import abc
import random
import time
from typing import Optional

ADAPTER_REGISTRY: dict[str, type["VMSAdapter"]] = {}


def register(adapter_type: str):
    def _wrap(cls):
        ADAPTER_REGISTRY[adapter_type] = cls
        cls.adapter_type = adapter_type
        return cls
    return _wrap


class VMSAdapter(abc.ABC):
    """Base class every vendor adapter implements."""

    vendor: str = "generic"
    adapter_type: str = "generic_rest"
    # Native event vocabulary this vendor emits (drives poll_events).
    event_types: list[str] = ["motion"]

    def __init__(self, system: dict):
        # `system` is a vms_systems row (dict-like).
        self.system = system
        self.name = system.get("name")
        self.base_url = system.get("base_url")
        self.auth_ref = system.get("auth_ref")  # name of a secret, never the secret

    def health(self) -> dict:
        """Connectivity probe. Mock: derive from the stored status field."""
        status = self.system.get("status") or "unknown"
        latency = None if status in ("offline", "unknown") else random.randint(20, 180)
        return {"status": status, "latency_ms": latency, "checked_at": time.time()}

    @abc.abstractmethod
    def list_cameras(self) -> list[dict]:
        """Cameras the source system exposes (external ids + labels)."""

    @abc.abstractmethod
    def poll_events(self, watch_values: Optional[list[str]] = None) -> list[dict]:
        """Return events observed since the last poll.

        `watch_values` are watchlist identifiers the federation layer wants the
        source system to flag if it can (a vendor that reports vehicle tags may echo a
        vehicle back). Each event dict:
          {external_event_id, camera_external_id, event_type, payload:{...}}
        """


def get_adapter(system: dict) -> VMSAdapter:
    cls = ADAPTER_REGISTRY.get(system.get("adapter_type"))
    if cls is None:
        raise ValueError(f"No adapter registered for type {system.get('adapter_type')!r}")
    return cls(system)
