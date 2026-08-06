"""
Global handling of database IntegrityError by custom_exception_handler.

A DB constraint violation (e.g. a duplicate-key unique-constraint breach) must
never surface as a raw HTTP 500 that leaks the SQL constraint. It must be
converted to the project's standard error envelope ({"error": <message>}) with a
clean, generic, non-technical message and an appropriate HTTP status, exactly
like the other cases already handled by custom_exception_handler.

This exercises the real DRF dispatch path so the request goes through
REST_FRAMEWORK['EXCEPTION_HANDLER'] just as a production request would.
"""

from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView


# Mirrors the real duplicate-key error text so the test can prove the raw SQL
# detail is never echoed back to the client.
_RAW_DB_MESSAGE = (
    'duplicate key value violates unique constraint '
    '"module_contacts_account_id_email_client_id_d5ea4433_uniq"'
)


class _BoomView(APIView):
    """Minimal view whose errors run through the configured EXCEPTION_HANDLER."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        raise IntegrityError(_RAW_DB_MESSAGE)


def _call_boom():
    factory = APIRequestFactory()
    request = factory.get('/boom')
    return _BoomView.as_view()(request)


def test_integrity_error_returns_clean_standardized_conflict():
    """IntegrityError -> clean 409 in the standard {"error": ...} envelope."""
    response = _call_boom()

    # A clean, deliberate status — never a raw 500.
    assert response.status_code == status.HTTP_409_CONFLICT

    # Same envelope shape the handler produces for every other case.
    assert isinstance(response.data, dict)
    assert set(response.data.keys()) == {"error"}


def test_integrity_error_message_does_not_leak_sql():
    """The response must carry a generic message, never the SQL constraint."""
    response = _call_boom()

    body = str(response.data["error"]).lower()
    assert "duplicate key" not in body
    assert "constraint" not in body
    assert "module_contacts" not in body
    # A human-readable, non-empty message is returned.
    assert body.strip()
