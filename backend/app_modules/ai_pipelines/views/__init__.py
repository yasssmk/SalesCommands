# app_modules/ai_pipelines/views/__init__.py
"""
Views package for ai_pipelines.

Re-exports the public view classes so callers (notably urls.py) can
import them from the package root:

    from app_modules.ai_pipelines.views import ActivityExtractionView

When new endpoints land (future game-plan generator, etc.), add their
view classes here and to __all__.
"""

from .activity_extraction_view import ActivityExtractionView
from .deal_health_view import DealHealthRunView
from .last_run_view import LastRunView


__all__ = ['ActivityExtractionView', 'DealHealthRunView', 'LastRunView']