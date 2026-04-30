# app_modules/signals/services/corroboration_service.py
"""
CorroborationService — corroboration count computation from canonical_key.

Never stores a count — always computed on demand from live data.
Works on any signal model carrying canonical_key AND source_contact.
In MVP, actively called for PeopleSignal only — but Pain / Objective
expose it via BaseSignalDetailSerializer.get_corroboration_count too.

Corroboration is defined as the number of DISTINCT source_contact values
that have produced a VALIDATED signal sharing the same canonical_key on
the same account.

Sprint TechStack — non-applicability
------------------------------------
TechStackSignal shadow-overrides source_contact to None on the model
(a tool's existence at an account is account-level, not contact-level —
see TechStackSignal model docstring). The "distinct contacts" notion
does not apply.

For TechStack, the equivalent metric lives at the CLUSTER level:
SignalClusterService produces a `confirmation_count` for each cluster
that aggregates by canonical_key alone — not by contact. The Detail
endpoint of an individual TechStackSignal therefore always reports
corroboration_count = 1 (the observation itself counts once); the
cluster surface is the right place to look at the breadth of evidence.

Both methods below are guarded with a class-level None-check on
source_contact so a TechStack signal returns 1 / {} silently rather
than crashing at SQL compile time on a non-existent field.
"""

from django.db.models import Count
from django.db.models.functions import Coalesce, Cast
from django.db.models import CharField, Value

from ..constants import SignalStatus


class CorroborationService:
    """
    Stateless service for corroboration count computation.

    All methods are classmethods — no instance needed.
    No writes, no caching — pure read computation.
    Caching is the caller's responsibility (view or serializer layer).
    """

    # =========================================================================
    # COMPUTE FOR SINGLE SIGNAL
    # =========================================================================

    @classmethod
    def compute_for_signal(cls, signal) -> int:
        """
        Return the corroboration count for a single signal instance.

        Counts DISTINCT source_contact values among all VALIDATED signals
        on the same account sharing the same canonical_key.

        Args:
            signal: Any concrete signal instance with a canonical_key field.

        Returns:
            int — corroboration count.
            Returns 1 if canonical_key is None (unanchored observation).
            Returns 1 if the concrete model shadow-overrides source_contact
            to None — TechStackSignal case, see module docstring.
        """
        if not signal.canonical_key:
            return 1

        model_class = type(signal)

        # Shadow-override guard — TechStackSignal has no source_contact
        # field; the concept of "distinct contributing contacts" does
        # not apply. Returning 1 keeps the API surface uniform without
        # forcing a per-type branch in the caller.
        if getattr(model_class, 'source_contact', None) is None:
            return 1

        return (
            model_class.objects
            .filter(
                account_id=signal.account_id,
                canonical_key=signal.canonical_key,
                status=SignalStatus.VALIDATED,
            )
            .aggregate(
                count=Count(
                    'source_contact_id',
                    distinct=True,
                )
            )['count'] or 1
        )

    # =========================================================================
    # BULK COMPUTE
    # =========================================================================

    @classmethod
    def bulk_compute(cls, account_id, model_class) -> dict:
        """
        Return corroboration counts for all VALIDATED signals on an account.

        Single query — use for list views that need counts across an entire
        account to avoid N+1 queries.

        Args:
            account_id:  UUID of the account.
            model_class: Concrete signal model class (e.g. PeopleSignal).

        Returns:
            dict mapping canonical_key (str) → count (int).
            Signals with canonical_key=None are excluded.
            Returns an empty dict if model_class shadow-overrides
            source_contact to None — TechStackSignal case, see module
            docstring. Callers expecting counts for those types should
            fall back to SignalClusterService.confirmation_count.

        Example:
            {
                'people:uuid-123:CHAMPION':    2,
                'people:uuid-456:BLOCKER':     1,
            }
        """
        # Shadow-override guard — same rationale as compute_for_signal.
        # Returning {} signals "no per-canonical-key counts available
        # for this model" and lets the caller decide whether to default
        # to 1 or to query the cluster service instead.
        if getattr(model_class, 'source_contact', None) is None:
            return {}

        rows = (
            model_class.objects
            .filter(
                account_id=account_id,
                status=SignalStatus.VALIDATED,
            )
            .exclude(canonical_key__isnull=True)
            .exclude(canonical_key='')
            .values('canonical_key')
            .annotate(
                count=Count('source_contact_id', distinct=True)
            )
        )

        return {
            row['canonical_key']: row['count'] or 1
            for row in rows
        }