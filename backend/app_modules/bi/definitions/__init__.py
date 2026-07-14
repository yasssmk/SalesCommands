# app_modules/bi/definitions/__init__.py
"""
KPI definitions.

Each submodule declares one or more KPIDefinition objects and exposes them in a
module-level ``KPIS`` list. ``load_all()`` registers them all — idempotently, so
it is safe to call at app startup (BIConfig.ready) and again from tests that
clear the registry.
"""

from app_modules.bi import registry

from . import activities as _activities
from . import campaigns as _campaigns
from . import decision_cycles as _decision_cycles
from . import leads as _leads
from . import territory as _territory

# Add new definition modules here as KPIs are declared.
_MODULES = [
    _decision_cycles,
    _activities,
    _leads,
    _territory,
    _campaigns,
]


def load_all() -> None:
    """Register every declared KPI. Idempotent: already-registered keys are
    skipped, so the registry can be restored after a test clears it."""
    for module in _MODULES:
        for kpi in getattr(module, 'KPIS', []):
            if not registry.is_registered(kpi.key):
                registry.register(kpi)
