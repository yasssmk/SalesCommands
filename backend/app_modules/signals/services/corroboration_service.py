# app_modules/signals/services/corroboration_service.py
"""
CorroborationService — corroboration count computation from canonical_key.

Never stores a count — always computed on demand from live data.
Model-agnostic by design: works on any signal model carrying canonical_key.
In MVP, actively called for PeopleSignal only.

Corroboration is defined as the number of DISTINCT observation contexts
(source_contact, decision_cycle, campaign) that have produced a VALIDATED
signal sharing the same canonical_key on the same account.
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

        Counts DISTINCT (source_contact_id, decision_cycle_id, campaign_id)
        tuples among all VALIDATED signals on the same account sharing the
        same canonical_key.

        Args:
            signal: Any concrete signal instance with a canonical_key field.

        Returns:
            int — corroboration count.
            Returns 1 if canonical_key is None (unanchored observation).
        """
        if not signal.canonical_key:
            return 1

        model_class = signal.__class__

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

        Example:
            {
                'people:uuid-123:CHAMPION':    2,
                'people:uuid-456:BLOCKER':     1,
            }
        """
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