"""Pluggable VMS adapter framework (Model 3 — VMS Federation & Middleware).

Each departmental Video Management System is integrated through an adapter that
implements a common interface. Adapters here are mock implementations that speak
each vendor's native event vocabulary; in production they would wrap the real
ONVIF/vendor SDK/REST client. The federation layer never talks to a VMS directly
— only through these adapters, so onboarding a new vendor is one new class.
"""
from app.adapters.base import VMSAdapter, get_adapter, ADAPTER_REGISTRY

__all__ = ["VMSAdapter", "get_adapter", "ADAPTER_REGISTRY"]
