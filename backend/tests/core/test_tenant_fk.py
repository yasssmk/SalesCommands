# backend/tests/core/test_tenant_fk.py
"""
UNIT — the central write-side FK guard, core/tenant_fk.py (TD-246, Lot 0 —
0.4). Locks its contract: tenant always, account only when asked (never
None), the SAME refusal for an unknown, foreign or malformed id (no existence
oracle), deduplication, empty inputs without query, and ONE query per call
(CaptureQueriesContext).

DB: Postgres.
"""

import uuid

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import serializers

from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact
from app_modules.core_modules.models import StandardDepartment
from core.constants import ACCOUNT_NOT_APPLICABLE
from core.error_messages import ContactErrorMessages, CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.tenant_fk import (
    TenantScopedPrimaryKeyRelatedField,
    check_resolved_scope,
    resolve_in_tenant,
    resolve_one_in_tenant,
)
from end_users.models import ClientAccount, User

from tests.signals.conftest import (  # noqa: F401
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    contact,
    contact_extra,
    other_tenant_contact,
    other_account,
    other_account_contact,
)

NOT_FOUND = str(CoreErrorMessages.OBJECT_NOT_FOUND)
INVALID_ACCOUNT = str(ContactErrorMessages.INVALID_ACCOUNT)


def _refusal(callable_, *args, **kwargs):
    """The detail of the StandardizedValidationError raised by the call."""
    with pytest.raises(StandardizedValidationError) as exc:
        callable_(*args, **kwargs)
    return exc.value.detail


@pytest.mark.django_db
class TestResolveInTenant:

    def test_own_ids_in_input_order_deduplicated(self, contact, contact_extra, client_account_a):
        ids = [contact_extra.id, str(contact.id), contact_extra.id]
        result = resolve_in_tenant(
            Contact, ids, client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
        )
        assert result == [contact_extra, contact]

    def test_exactly_one_query_with_account_check(
        self, contact, contact_extra, account, client_account_a
    ):
        with CaptureQueriesContext(connection) as cap:
            result = resolve_in_tenant(
                Contact, [contact.id, contact_extra.id, contact.id],
                client_id=client_account_a.id, account_id=account,
            )
        assert len(result) == 2
        assert len(cap.captured_queries) == 1

    @pytest.mark.parametrize('empty', [None, [], ()])
    def test_empty_input_no_query(self, empty, client_account_a):
        with CaptureQueriesContext(connection) as cap:
            assert resolve_in_tenant(
                Contact, empty, client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
            ) == []
        assert len(cap.captured_queries) == 0

    def test_foreign_unknown_malformed_and_mixed_are_the_same_refusal(
        self, contact, other_tenant_contact, client_account_a
    ):
        kw = dict(client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE)
        details = [
            _refusal(resolve_in_tenant, Contact, [other_tenant_contact.id], **kw),
            _refusal(resolve_in_tenant, Contact, [uuid.uuid4()], **kw),
            _refusal(resolve_in_tenant, Contact, ['not-a-uuid'], **kw),
            _refusal(resolve_in_tenant, Contact, [contact.id, other_tenant_contact.id], **kw),
        ]
        assert all(d == details[0] for d in details), details
        assert str(details[0]['error']) == NOT_FOUND

    def test_other_account_is_invalid_account(
        self, contact, other_account_contact, account, client_account_a
    ):
        detail = _refusal(
            resolve_in_tenant, Contact, [contact.id, other_account_contact.id],
            client_id=client_account_a.id, account_id=account.id,
        )
        assert str(detail['error']) == INVALID_ACCOUNT

    def test_account_not_applicable_skips_the_account_check(
        self, other_account_contact, client_account_a
    ):
        assert resolve_in_tenant(
            Contact, [other_account_contact.id],
            client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
        ) == [other_account_contact]

    @pytest.mark.parametrize('ids', [None, [], ['x']])
    def test_account_id_none_is_a_programming_error(self, ids, client_account_a):
        with pytest.raises(ImproperlyConfigured):
            resolve_in_tenant(Contact, ids, client_id=client_account_a.id, account_id=None)

    def test_missing_tenant_is_refused_not_unfiltered(self, contact):
        detail = _refusal(
            resolve_in_tenant, Contact, [contact.id],
            client_id=None, account_id=ACCOUNT_NOT_APPLICABLE,
        )
        assert str(detail['error']) == NOT_FOUND

    def test_model_without_tenant_field_is_a_programming_error(self, client_account_a):
        dept, _ = StandardDepartment.objects.get_or_create(
            name=StandardDepartment.DepartmentChoices.HR
        )
        with pytest.raises(ImproperlyConfigured):
            resolve_in_tenant(
                StandardDepartment, [dept.id],
                client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
            )

    def test_account_check_on_model_without_account_field_is_a_programming_error(
        self, account, client_account_a
    ):
        with pytest.raises(ImproperlyConfigured):
            resolve_in_tenant(
                CompanyAccount, [account.id],
                client_id=client_account_a.id, account_id=account.id,
            )

    def test_single_id_passed_as_list_api_is_a_programming_error(self, contact, client_account_a):
        with pytest.raises(ImproperlyConfigured):
            resolve_in_tenant(
                Contact, str(contact.id),
                client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
            )

    def test_base_queryset_is_respected(self, contact, contact_extra, client_account_a):
        detail = _refusal(
            resolve_in_tenant, Contact.objects.filter(first_name='Jane'), [contact_extra.id],
            client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
        )
        assert str(detail['error']) == NOT_FOUND

    def test_tenant_root_and_client_account_models(
        self, client_account_a, client_account_b, user_a, user_b
    ):
        kw = dict(client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE)
        assert resolve_in_tenant(ClientAccount, [client_account_a.id], **kw) == [client_account_a]
        assert resolve_in_tenant(User, [user_a.id], **kw) == [user_a]
        assert str(_refusal(resolve_in_tenant, ClientAccount, [client_account_b.id], **kw)['error']) == NOT_FOUND
        assert str(_refusal(resolve_in_tenant, User, [user_b.id], **kw)['error']) == NOT_FOUND


@pytest.mark.django_db
class TestResolveOneInTenant:

    def test_none_is_none_without_query(self, client_account_a):
        with CaptureQueriesContext(connection) as cap:
            assert resolve_one_in_tenant(
                Contact, None, client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
            ) is None
        assert len(cap.captured_queries) == 0

    def test_none_still_requires_an_account_decision(self, client_account_a):
        with pytest.raises(ImproperlyConfigured):
            resolve_one_in_tenant(Contact, None, client_id=client_account_a.id, account_id=None)

    def test_own_and_foreign(self, contact, other_tenant_contact, account, client_account_a):
        assert resolve_one_in_tenant(
            Contact, contact.id, client_id=client_account_a.id, account_id=account,
        ) == contact
        detail = _refusal(
            resolve_one_in_tenant, Contact, other_tenant_contact.id,
            client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
        )
        assert str(detail['error']) == NOT_FOUND


@pytest.mark.django_db
class TestCheckResolvedScope:

    def test_own_instances_pass_without_query(self, contact, contact_extra, account, client_account_a):
        with CaptureQueriesContext(connection) as cap:
            check_resolved_scope(
                {'account': account, 'contact': contact, 'people': [contact_extra], 'title': 'x'},
                client_id=client_account_a.id, account_id=account.id, skip=('account',),
            )
        assert len(cap.captured_queries) == 0

    def test_foreign_instance_or_list_item_is_not_found(
        self, contact, other_tenant_contact, client_account_a
    ):
        for values in ({'contact': other_tenant_contact},
                       {'people': [contact, other_tenant_contact]}):
            detail = _refusal(
                check_resolved_scope, values,
                client_id=client_account_a.id, account_id=ACCOUNT_NOT_APPLICABLE,
            )
            assert str(detail['error']) == NOT_FOUND

    def test_other_account_is_invalid_account_unless_skipped_or_not_applicable(
        self, other_account_contact, account, client_account_a
    ):
        values = {'contact': other_account_contact}
        detail = _refusal(
            check_resolved_scope, values, client_id=client_account_a.id, account_id=account.id,
        )
        assert str(detail['error']) == INVALID_ACCOUNT
        check_resolved_scope(values, client_id=client_account_a.id, account_id=account.id,
                             skip=('contact',))
        check_resolved_scope(values, client_id=client_account_a.id,
                             account_id=ACCOUNT_NOT_APPLICABLE)

    def test_global_instances_are_out_of_scope(self, client_account_a):
        dept, _ = StandardDepartment.objects.get_or_create(
            name=StandardDepartment.DepartmentChoices.FINANCE
        )
        check_resolved_scope({'target_departments': [dept]}, client_id=client_account_a.id,
                             account_id=ACCOUNT_NOT_APPLICABLE)

    def test_missing_tenant_refuses_any_tenant_instance(self, contact):
        detail = _refusal(check_resolved_scope, {'contact': contact},
                          client_id=None, account_id=ACCOUNT_NOT_APPLICABLE)
        assert str(detail['error']) == NOT_FOUND

    def test_account_id_none_is_a_programming_error(self, contact, client_account_a):
        with pytest.raises(ImproperlyConfigured):
            check_resolved_scope({'contact': contact}, client_id=client_account_a.id, account_id=None)


class _LinkSerializer(serializers.Serializer):
    contact = TenantScopedPrimaryKeyRelatedField(
        queryset=Contact.objects.all(), required=False, allow_null=True,
    )
    people = TenantScopedPrimaryKeyRelatedField(
        queryset=Contact.objects.all(), many=True, required=False,
    )


@pytest.mark.django_db
class TestTenantScopedField:

    def test_own_ids_resolve(self, contact, contact_extra, client_account_a):
        s = _LinkSerializer(
            data={'contact': str(contact.id), 'people': [str(contact.id), str(contact_extra.id)]},
            context={'client_id': client_account_a.id},
        )
        assert s.is_valid(), s.errors
        assert s.validated_data['contact'] == contact
        assert s.validated_data['people'] == [contact, contact_extra]

    def test_null_is_allowed(self, client_account_a):
        s = _LinkSerializer(data={'contact': None}, context={'client_id': client_account_a.id})
        assert s.is_valid(), s.errors
        assert s.validated_data['contact'] is None

    def test_unknown_and_foreign_give_identical_errors(
        self, other_tenant_contact, client_account_a
    ):
        ctx = {'client_id': client_account_a.id}
        unknown = _LinkSerializer(data={'contact': str(uuid.uuid4())}, context=ctx)
        foreign = _LinkSerializer(data={'contact': str(other_tenant_contact.id)}, context=ctx)
        assert not unknown.is_valid() and not foreign.is_valid()
        assert unknown.errors == foreign.errors
        assert NOT_FOUND in str(foreign.errors)

    def test_many_resolves_in_one_query(self, contact, contact_extra, client_account_a):
        s = _LinkSerializer(
            data={'people': [str(contact.id), str(contact_extra.id)]},
            context={'client_id': client_account_a.id},
        )
        with CaptureQueriesContext(connection) as cap:
            assert s.is_valid(), s.errors
        assert len(cap.captured_queries) == 1

    def test_no_tenant_in_context_refuses(self, contact):
        s = _LinkSerializer(data={'contact': str(contact.id)}, context={})
        assert not s.is_valid()
        assert NOT_FOUND in str(s.errors)
