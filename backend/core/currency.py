# core/currency.py
"""
The tenant's currency, resolved in ONE place.

A tenant has exactly one currency (``ClientAccount.currency``) and every amount
it owns is expressed in it: product prices, deal lines, cycle totals, KPI
figures, quota targets. There is no conversion, no FX rate, no per-deal or
per-product currency, and nothing ever sums across currencies — a tenant's rows
all share its own.

So the currency is never COPIED onto a deal or a line: it is read from the
tenant when a payload is built. This module is that read, in one function, so a
second (and eventually divergent) resolution cannot appear — the lesson of the
manual-amount / derived-roll-up split earlier in this sprint.

The choice list lives in ``core.constants.CURRENCY`` (shared with the field's
``choices``); extend it there and both the field and this helper follow.
"""

from core.constants import CURRENCY


# Used when a tenant cannot be resolved (an unauthenticated or fixture-built
# payload). Matches ClientAccount.currency's own default, so a caller never sees
# a different unit depending on which path produced the number.
DEFAULT_CURRENCY = 'EUR'

SUPPORTED_CURRENCIES = tuple(code for code, _label in CURRENCY)


def tenant_currency(client_id):
    """The ISO-4217 code for ``client_id``, or DEFAULT_CURRENCY if unknown.

    ONE query, values_list only — cheap enough to call per payload, and never
    raising: a missing tenant degrades to the default rather than breaking a
    read that is otherwise fine.
    """
    if not client_id:
        return DEFAULT_CURRENCY

    from end_users.models import ClientAccount

    code = (
        ClientAccount.objects
        .filter(pk=client_id)
        .values_list('currency', flat=True)
        .first()
    )
    return code or DEFAULT_CURRENCY


class TenantCurrencySerializerMixin:
    """Adds a ``currency`` field resolved from the row's tenant, ONCE per pass.

    A list serializes many rows of the SAME tenant, so resolving per row would
    be an N+1 (caught by the DC list's query-count guard). The memo is held on
    the serializer instance — its life is one serialization pass, so a tenant
    that changes currency is never served a stale one — and keyed by client_id,
    so it stays correct even if a pass ever mixed tenants.

    Consumers declare ``currency = serializers.SerializerMethodField()`` and add
    'currency' to Meta.fields.
    """

    def get_currency(self, obj):
        memo = getattr(self, '_tenant_currency_memo', None)
        if memo is None:
            memo = self._tenant_currency_memo = {}

        key = str(getattr(obj, 'client_id', '') or '')
        if key not in memo:
            memo[key] = tenant_currency(obj.client_id)
        return memo[key]
