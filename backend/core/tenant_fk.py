# core/tenant_fk.py
"""
WRITE-SIDE FK GUARD — the central control of foreign keys received in a
payload (TD-246, Lot 0 sécurité 0.4).

Every id a client sends to LINK an object (FK, M2M, an id handed to a service)
must belong to the requester's TENANT, and — when the caller says so — to the
right ACCOUNT. This module is the one place that does it. Any new FK written
from a payload goes through it (ROADMAP, « Principes transverses »).

THE RULES
---------
* Tenant, always. The tenant field of a model is resolved by
  ``core.client_scope.tenant_lookup`` (ClientAccount pk / ``client_account`` /
  ``client_id``) — the same rule as the read-side filter of the views. A model
  with no tenant field (a global list such as StandardDepartment) is NOT for
  this helper: ``ImproperlyConfigured``.
* No existence oracle. An id that does not exist, an id of ANOTHER tenant and a
  malformed id give EXACTLY the same answer: HTTP 400
  ``{"error": "Object not found or access denied"}``
  (``CoreErrorMessages.OBJECT_NOT_FOUND``), through the same code path. A
  missing tenant (no ``client_id``) is refused the same way — never resolved
  unfiltered.
* Account, only when the caller asks — never implicit, never guessed.
  ``account_id`` is a MANDATORY keyword: pass the reference account (id or
  instance), or ``ACCOUNT_NOT_APPLICABLE`` (core/constants.py) when the
  object has no account to match. ``None`` raises ``ImproperlyConfigured``
  (a programming error that must break the tests). Checked AFTER the tenant;
  a mismatch (or an object with no account) is HTTP 400
  ``ContactErrorMessages.INVALID_ACCOUNT`` — it only reveals objects of the
  requester's OWN tenant.
* One query per call, not one per id. Ids are deduplicated (order kept, a
  repeated valid id is accepted); ``None`` / ``[]`` resolve to ``None`` /
  ``[]`` with no query.

THE FOUR USAGES
---------------
1. A service with raw ids (e.g. a ``create-with-entities`` style service)::

       from core.constants import ACCOUNT_NOT_APPLICABLE
       from core.tenant_fk import resolve_in_tenant, resolve_one_in_tenant

       contacts = resolve_in_tenant(
           Contact, payload.get('contact_ids'),
           client_id=self.client_id, account_id=activity.account_id,
       )
       cycle = resolve_one_in_tenant(
           DecisionCycle, payload.get('decision_cycle_id'),
           client_id=self.client_id, account_id=ACCOUNT_NOT_APPLICABLE,
       )

2. A serializer with a plain UUID field, in ``validate_<field>`` — or in
   ``validate()`` when the account comes from another field::

       territory_ids = serializers.ListField(child=serializers.UUIDField(), required=False)

       def validate_territory_ids(self, value):
           return resolve_in_tenant(
               Territory, value,
               client_id=self._get_client_id_from_context(),
               account_id=ACCOUNT_NOT_APPLICABLE,
           )

       def validate(self, attrs):
           account = attrs.get('account') or self.instance.account
           attrs['contacts'] = resolve_in_tenant(
               Contact, attrs.pop('contact_ids', None),
               client_id=self._get_client_id_from_context(), account_id=account,
           )
           return attrs

3. A relational serializer field — the tenant is applied at RESOLUTION (one
   query for ``many=True``); its tenant comes from the serializer context
   (``context['client_id']`` or the JWT ``client_account`` of
   ``context['request']``), so a serializer built without tenant refuses::

       contact = TenantScopedPrimaryKeyRelatedField(
           queryset=Contact.objects.all(), required=False, allow_null=True,
       )
       suggested_contacts = TenantScopedPrimaryKeyRelatedField(
           queryset=Contact.objects.all(), many=True, required=False,
       )

   The field checks the tenant only; the account (which depends on another
   field) is checked in ``validate()`` with usage 4.

   For a ModelSerializer whose FKs are AUTO-generated from ``Meta.fields``,
   ``TenantScopedRelationsMixin`` makes every auto FK / M2M towards a
   tenant model a TenantScopedPrimaryKeyRelatedField (a FK towards a global
   list such as StandardDepartment keeps DRF's field) — present and future
   fields alike::

       class MySignalCreateSerializer(TenantScopedRelationsMixin,
                                      serializers.ModelSerializer):
           class Meta:
               model = MySignal
               fields = ['account', 'contact', 'people']

4. The safety net on already-resolved instances — ``check_resolved_scope``
   walks the validated ``attrs`` (instances and lists of instances), no
   query: tenant of every instance, then account (``skip`` the reference
   field itself)::

       def validate(self, attrs):
           account = attrs.get('account')
           check_resolved_scope(
               attrs,
               client_id=self._get_client_id_from_context(),
               account_id=account.pk if account else ACCOUNT_NOT_APPLICABLE,
               skip=('account',),
           )
           return attrs
"""

from django.core.exceptions import ImproperlyConfigured, ValidationError as DjangoValidationError
from django.db import models
from django.db.models import QuerySet
from rest_framework import serializers
from rest_framework.relations import MANY_RELATION_KWARGS, ManyRelatedField

from core.client_scope import tenant_lookup
from core.constants import ACCOUNT_NOT_APPLICABLE
from core.error_messages import ContactErrorMessages, CoreErrorMessages
from core.exceptions import StandardizedValidationError


# =============================================================================
# INTERNALS
# =============================================================================

def _not_found():
    """THE refusal of an id that is unknown, foreign or malformed."""
    return StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)


def _base_queryset(model_or_queryset):
    if isinstance(model_or_queryset, QuerySet):
        return model_or_queryset
    return model_or_queryset._default_manager.all()


def _account_pk(account_id):
    """The reference account pk, None for ACCOUNT_NOT_APPLICABLE; ``None``
    itself is a programming error (the check must be decided, not guessed)."""
    if account_id is ACCOUNT_NOT_APPLICABLE:
        return None
    if account_id is None:
        raise ImproperlyConfigured(
            'account_id=None: pass the reference account, or '
            'ACCOUNT_NOT_APPLICABLE when no account applies (core/tenant_fk.py).'
        )
    if isinstance(account_id, models.Model):
        return account_id.pk
    return account_id


def _account_attname(model, account_field):
    try:
        return model._meta.get_field(account_field).attname
    except Exception:
        raise ImproperlyConfigured(
            f'{model.__name__} has no "{account_field}" field: an account '
            'check cannot apply to it (pass ACCOUNT_NOT_APPLICABLE).'
        )


def _tenant_lookup_or_fail(model, client_id):
    lookup = tenant_lookup(model, client_id)
    if lookup is None:
        raise ImproperlyConfigured(
            f'{model.__name__} has no tenant field: core/tenant_fk.py only '
            'resolves tenant data (a global list keeps its own check).'
        )
    return lookup


def _normalize_pk(model, value):
    """The pk as the DB expects it; malformed → the same refusal as unknown."""
    if isinstance(value, models.Model):
        value = value.pk
    try:
        return model._meta.pk.to_python(value)
    except (DjangoValidationError, TypeError, ValueError):
        raise _not_found()


def _instance_tenant(obj):
    """The tenant value carried by an instance, or None if its model has no
    tenant field (global list — out of scope by construction)."""
    lookup = tenant_lookup(type(obj), '__probe__')
    if lookup is None:
        return None
    (field,) = lookup
    return obj.pk if field == 'pk' else getattr(obj, field)


# =============================================================================
# PUBLIC API
# =============================================================================

def resolve_in_tenant(model, ids, *, client_id, account_id, account_field='account'):
    """
    The instances of ``ids`` (a list / tuple / set; deduplicated, input order
    kept), every one of the tenant ``client_id`` and — unless ``account_id`` is
    ACCOUNT_NOT_APPLICABLE — of the account ``account_id``.

    ``model`` may be a model or a base queryset (the tenant filter is added on
    top). One query; ``None`` / empty → ``[]`` without query.
    """
    account_pk = _account_pk(account_id)
    if ids is None:
        return []
    if isinstance(ids, (str, bytes, models.Model)) or not hasattr(ids, '__iter__'):
        raise ImproperlyConfigured(
            'resolve_in_tenant expects a list of ids — use resolve_one_in_tenant '
            'for a single id.'
        )

    base = _base_queryset(model)
    model_cls = base.model
    unique = list(dict.fromkeys(_normalize_pk(model_cls, value) for value in ids))
    if not unique:
        return []
    if not client_id:
        raise _not_found()

    lookup = _tenant_lookup_or_fail(model_cls, client_id)
    attname = _account_attname(model_cls, account_field) if account_pk is not None else None

    found = {obj.pk: obj for obj in base.filter(pk__in=unique, **lookup)}
    if len(found) != len(unique):
        raise _not_found()

    if attname is not None:
        for obj in found.values():
            if str(getattr(obj, attname)) != str(account_pk):
                raise StandardizedValidationError(ContactErrorMessages.INVALID_ACCOUNT)

    return [found[pk] for pk in unique]


def resolve_one_in_tenant(model, pk, *, client_id, account_id, account_field='account'):
    """The instance of ``pk`` under the same rules; ``None`` → ``None`` without
    query (clearing a nullable FK stays possible)."""
    _account_pk(account_id)  # the account decision is enforced even for None
    if pk is None:
        return None
    return resolve_in_tenant(
        model, [pk], client_id=client_id, account_id=account_id,
        account_field=account_field,
    )[0]


def check_resolved_scope(values, *, client_id, account_id, account_field='account', skip=()):
    """
    Safety net on instances ALREADY resolved (e.g. a serializer's validated
    ``attrs``): no query. ``values`` maps names to an instance or to a list of
    instances; other values are ignored.

    Tenant first: any instance carrying a tenant must be of ``client_id``,
    else OBJECT_NOT_FOUND. Then the account — unless ``account_id`` is
    ACCOUNT_NOT_APPLICABLE — for every instance (the names in ``skip``
    excluded, typically the reference ``account`` itself) whose model has an
    ``account_field``, else INVALID_ACCOUNT.
    """
    account_pk = _account_pk(account_id)

    resolved = []
    for name, value in values.items():
        if isinstance(value, models.Model):
            resolved.append((name, value))
        elif isinstance(value, (list, tuple, QuerySet)):
            resolved.extend((name, item) for item in value if isinstance(item, models.Model))

    for _name, obj in resolved:
        tenant = _instance_tenant(obj)
        if tenant is not None and (not client_id or str(tenant) != str(client_id)):
            raise _not_found()

    if account_pk is None:
        return
    for name, obj in resolved:
        if name in skip:
            continue
        try:
            attname = type(obj)._meta.get_field(account_field).attname
        except Exception:
            continue
        if str(getattr(obj, attname)) != str(account_pk):
            raise StandardizedValidationError(ContactErrorMessages.INVALID_ACCOUNT)


def context_client_id(context):
    """The tenant of a serializer context: ``context['client_id']`` if the
    caller injected it, else the JWT ``client_account`` claim of
    ``context['request']``; None when there is none (→ refusal)."""
    client_id = context.get('client_id')
    if client_id:
        return client_id
    request = context.get('request')
    auth = getattr(request, 'auth', None) if request is not None else None
    if auth is None or not hasattr(auth, 'get'):
        return None
    return auth.get('client_account') or None


# =============================================================================
# SERIALIZER FIELDS
# =============================================================================

class TenantScopedManyRelatedField(ManyRelatedField):
    """``many=True`` version: the whole list in ONE query (DRF's
    ManyRelatedField does one per id)."""

    def to_internal_value(self, data):
        if isinstance(data, str) or not hasattr(data, '__iter__'):
            self.fail('not_a_list', input_type=type(data).__name__)
        if not self.allow_empty and len(data) == 0:
            self.fail('empty')
        child = self.child_relation
        return resolve_in_tenant(
            child.get_queryset(), list(data),
            client_id=context_client_id(child.context),
            account_id=ACCOUNT_NOT_APPLICABLE,
        )


class TenantScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """A PrimaryKeyRelatedField resolved INSIDE the requester's tenant (usage
    3 of the module docstring): unknown, foreign and malformed ids get the
    same OBJECT_NOT_FOUND answer; no tenant in the context → refused. Tenant
    only — the account is checked in validate()."""

    @classmethod
    def many_init(cls, *args, **kwargs):
        list_kwargs = {'child_relation': cls(*args, **kwargs)}
        for key in kwargs:
            if key in MANY_RELATION_KWARGS:
                list_kwargs[key] = kwargs[key]
        return TenantScopedManyRelatedField(**list_kwargs)

    def to_internal_value(self, data):
        return resolve_one_in_tenant(
            self.get_queryset(), data,
            client_id=context_client_id(self.context),
            account_id=ACCOUNT_NOT_APPLICABLE,
        )


class TenantScopedRelationsMixin:
    """ModelSerializer mixin (usage 3): every AUTO-generated FK / M2M field
    towards a model carrying a tenant is a TenantScopedPrimaryKeyRelatedField;
    one towards a global list keeps DRF's PrimaryKeyRelatedField. Explicitly
    declared fields are untouched."""

    def build_relational_field(self, field_name, relation_info):
        field_class, field_kwargs = super().build_relational_field(field_name, relation_info)
        if (field_class is serializers.PrimaryKeyRelatedField
                and tenant_lookup(relation_info.related_model, client_id=None) is not None):
            field_class = TenantScopedPrimaryKeyRelatedField
        return field_class, field_kwargs
