# app_modules/notifications/views/views.py
"""
Views for the Notifications module.

All views are BaseAPIView subclasses (client scoping via ViewMixin,
standard pagination, central handle_exception). Every query is scoped to
BOTH the caller's tenant (client_id) and the caller as recipient, so a
user only ever sees or mutates their own notifications.
"""

from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from core.error_messages import NotificationErrorMessages

from ..models import Notification
from ..serializers import NotificationSerializer


_TRUTHY = ('1', 'true', 'yes')


class NotificationListView(BaseAPIView):
    """
    GET /notifications/          -> paginated list of the caller's notifications
    GET /notifications/?unread=true -> only unread notifications
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    entity_name = 'notification'

    def _recipient_queryset(self, request):
        """Notifications scoped to the caller's tenant AND the caller."""
        queryset = self.filter_queryset_by_client(Notification.objects.all())
        return queryset.filter(recipient=request.user)

    def get(self, request):
        queryset = self._recipient_queryset(request)

        unread_param = request.query_params.get('unread')
        if unread_param and unread_param.lower() in _TRUTHY:
            queryset = queryset.filter(read_at__isnull=True)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = NotificationSerializer(page, many=True, context={'request': request})
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            })

        serializer = NotificationSerializer(queryset, many=True, context={'request': request})
        return Response({'success': True, 'data': serializer.data})


class NotificationUnreadCountView(BaseAPIView):
    """
    GET /notifications/unread-count/ -> { count } of the caller's unread notifications.
    Lightweight polling target for the notification bell badge.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    entity_name = 'notification'

    def get(self, request):
        count = self.filter_queryset_by_client(
            Notification.objects.all()
        ).filter(recipient=request.user, read_at__isnull=True).count()
        return Response({'success': True, 'data': {'count': count}})


class NotificationMarkReadView(BaseAPIView):
    """
    POST /notifications/{pk}/read/ -> mark the caller's notification as read.
    Idempotent: a second call on an already-read notification is a no-op 200.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    entity_name = 'notification'

    def post(self, request, pk):
        notification = self.filter_queryset_by_client(
            Notification.objects.all()
        ).filter(recipient=request.user, pk=pk).first()

        if notification is None:
            raise NotFound(NotificationErrorMessages.NOTIFICATION_NOT_FOUND)

        # Idempotent: only flip on the first read.
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(user=request.user)

        serializer = NotificationSerializer(notification, context={'request': request})
        return Response({'success': True, 'data': serializer.data})
