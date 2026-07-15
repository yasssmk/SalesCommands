# app_modules/notifications/urls.py
"""
URL configuration for the Notifications module.

Follows the same lazy get_urlpatterns() pattern as the accounts module.
"""

from django.urls import path

app_name = 'module_notifications'


# Lazy imports to avoid circular import
def get_urlpatterns():
    from .views import (
        NotificationListView,
        NotificationUnreadCountView,
        NotificationMarkReadView,
        NotificationRespondView,
    )

    return [
        # =====================================================================
        # UNREAD COUNT - Must be before CRUD to avoid conflict with {pk}
        # =====================================================================
        path('unread-count/', NotificationUnreadCountView.as_view(), name='unread-count'),

        # =====================================================================
        # MARK READ
        # =====================================================================
        path('<uuid:pk>/read/', NotificationMarkReadView.as_view(), name='mark-read'),

        # =====================================================================
        # RESPOND (accept/decline an actionable notification)
        # =====================================================================
        path('<uuid:pk>/respond/', NotificationRespondView.as_view(), name='respond'),

        # =====================================================================
        # LIST
        # =====================================================================
        path('', NotificationListView.as_view(), name='list'),
    ]


urlpatterns = get_urlpatterns()
