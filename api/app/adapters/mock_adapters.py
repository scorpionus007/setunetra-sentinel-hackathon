"""Mock vendor adapters — Hikvision, Milestone, CP-Plus, Genetec, ONVIF.

Each speaks its own event vocabulary. Some systems report vehicle tags from their
own edge devices; when the federation layer asks, they echo back a watched vehicle,
which is what lets the cross-system correlation engine link the same vehicle across
two VMS + the registry watchlist. All data is synthetic and clearly attributed to
the source system — this platform runs NO inference of its own, it only aggregates
and correlates what each source system reports.
"""
from __future__ import annotations

import random
import uuid
from typing import Optional

from app.adapters.base import VMSAdapter, register

_ZONES = ["north", "south", "gate", "lobby", "lane-1", "lane-2", "perimeter"]


def _eid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


class _MockBase(VMSAdapter):
    reports_vehicle_tags = False
    _camera_pool: list[str] = []

    def list_cameras(self) -> list[dict]:
        return [{"camera_external_id": c, "label": f"{self.vendor} cam {c}"} for c in self._camera_pool]

    def poll_events(self, watch_values: Optional[list[str]] = None) -> list[dict]:
        events: list[dict] = []
        # A couple of routine native events.
        for _ in range(random.randint(1, 3)):
            cam = random.choice(self._camera_pool) if self._camera_pool else "1"
            etype = random.choice(self.event_types)
            events.append({
                "external_event_id": _eid(self.vendor[:3].upper()),
                "camera_external_id": cam,
                "event_type": etype,
                "payload": {"zone": random.choice(_ZONES), "source": self.name},
            })
        # Vendors that report vehicle tags echo a watched vehicle so correlation can fire.
        if self.reports_vehicle_tags and watch_values:
            plate = watch_values[0]
            cam = self._camera_pool[0] if self._camera_pool else "1"
            events.append({
                "external_event_id": _eid("LPR"),
                "camera_external_id": cam,
                "event_type": "vehicle_tag",
                "payload": {"plate": plate, "source": self.name, "confidence_reported": "vendor"},
            })
        return events


@register("hikvision")
class HikvisionAdapter(_MockBase):
    vendor = "Hikvision"
    reports_vehicle_tags = True
    event_types = ["motion", "line_crossing", "tamper", "vehicle_tag"]
    _camera_pool = ["2", "13", "14", "15"]


@register("milestone")
class MilestoneAdapter(_MockBase):
    vendor = "Milestone"
    reports_vehicle_tags = True
    event_types = ["motion", "analytic_tag", "vehicle_tag", "door"]
    _camera_pool = ["1", "4", "5", "6", "16", "29"]


@register("cpplus")
class CPPlusAdapter(_MockBase):
    vendor = "CP-Plus"
    reports_vehicle_tags = False
    event_types = ["motion", "door_open", "offline"]
    _camera_pool = ["12", "17"]


@register("genetec")
class GenetecAdapter(_MockBase):
    vendor = "Genetec"
    reports_vehicle_tags = True
    event_types = ["motion", "intrusion", "vehicle_tag"]
    _camera_pool = ["18", "30"]


@register("onvif")
class OnvifAdapter(_MockBase):
    vendor = "ONVIF"
    reports_vehicle_tags = False
    event_types = ["motion", "offline"]
    _camera_pool = ["11", "19", "20", "23"]


@register("rtsp")
class RtspAdapter(_MockBase):
    vendor = "RTSP"
    reports_vehicle_tags = False
    event_types = ["motion"]
    _camera_pool = []


@register("generic_rest")
class GenericRestAdapter(_MockBase):
    vendor = "Generic"
    reports_vehicle_tags = False
    event_types = ["motion", "offline"]
    _camera_pool = []
