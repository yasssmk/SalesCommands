"""
Real-path handling of IntegrityError for views that override handle_exception.

The Fix.1 test used a plain DRF APIView, whose errors flow through DRF's default
handle_exception -> the configured EXCEPTION_HANDLER (custom_exception_handler).
But the real Contact view inherits BaseAPIView, which OVERRIDES handle_exception
and never calls that handler — so Fix.1 alone never ran on the real path and the
raw SQL still leaked as "An unexpected error occurred: duplicate key ...".

This test exercises the real method on the real view class, so the
IntegrityError -> clean 409 guarantee is proven on the path the UI actually hits.
"""

from django.db import IntegrityError
from rest_framework import status

from app_modules.contacts.views.views import ContactViewSet


_RAW_DB_MESSAGE = (
    'duplicate key value violates unique constraint '
    '"module_contacts_account_id_email_client_id_d5ea4433_uniq"'
)


def _handle_on_real_view():
    """Call the exact handle_exception DRF dispatch would invoke on this view."""
    view = ContactViewSet()
    view.request = None
    view.kwargs = {}
    return view.handle_exception(IntegrityError(_RAW_DB_MESSAGE))


def test_contact_view_integrity_error_is_clean_conflict():
    """Real path: IntegrityError -> clean 409 in the standard {"error": ...}."""
    response = _handle_on_real_view()

    assert response.status_code == status.HTTP_409_CONFLICT
    assert isinstance(response.data, dict)
    assert set(response.data.keys()) == {"error"}


def test_contact_view_integrity_error_does_not_leak_sql():
    """Real path: no SQL / constraint leak, and not the old raw-500 message."""
    response = _handle_on_real_view()

    body = str(response.data["error"]).lower()
    assert "duplicate key" not in body
    assert "constraint" not in body
    assert "module_contacts" not in body
    # The pre-fix behaviour returned CoreErrorMessages.UNEXPECTED_ERROR here.
    assert "an unexpected error occurred" not in body
    assert body.strip()
