"""
Core views package.

Contains views for cross-cutting concerns:
- operation_views: Operation status polling for long-running tasks
"""

from .operation_views import OperationStatusView

__all__ = [
    'OperationStatusView',
]