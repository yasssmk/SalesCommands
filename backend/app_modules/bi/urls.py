# app_modules/bi/urls.py
"""
URL configuration for the BI module.

Follows the same lazy get_urlpatterns() pattern as the notifications module.
"""

from django.urls import path

app_name = 'module_bi'


# Lazy imports to avoid circular import at module load.
def get_urlpatterns():
    from .views import (
        KPIDetailView, KPIBatchView, TeamTodoListView, TodoListView,
    )

    return [
        # Batch MUST come before the <key> route so 'batch' is not captured as a key.
        path('kpi/batch/', KPIBatchView.as_view(), name='kpi-batch'),
        path('kpi/<str:key>/', KPIDetailView.as_view(), name='kpi-detail'),
        # Todo rows — the list counterpart of the todo_my_windows counts.
        path('todo/', TodoListView.as_view(), name='todo-list'),
        # Team todo rows — the manager view, row twin of todo_team_by_owner.
        path('todo/team/', TeamTodoListView.as_view(), name='todo-team-list'),
    ]


urlpatterns = get_urlpatterns()
