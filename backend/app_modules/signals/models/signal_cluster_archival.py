# app_modules/signals/models/signal_cluster_archival.py
"""
SignalClusterArchival — per-tenant archival flag for signal clusters.

A "cluster" is the set of signals sharing the same canonical_key on a
given account. Clusters are computed on read by SignalClusterService —
they are NOT a stored entity. This model exists solely to remember the
archival state of a cluster so the listing endpoint can hide it by
default.

Design choices
--------------
1. Generic signal_type field (not Pain-only)
   The same table serves Pain, Objective, Impact and TechStack clusters
   without a schema change.

2. Archival = a row with unarchived_at = NULL
   Unarchive sets unarchived_at to the current time. The row is kept
   for audit. A future re-archive must INSERT a new row (enforced by
   the conditional unique constraint below).

3. Ownership
   SignalClusterArchival is NOT registered in OWNERSHIP_MAP (ownership
   registry is deferred for the module). Access control lives on the
   Signals module as a whole via ScopedPermission — if the caller can
   see the account's signals, they can archive/unarchive clusters on
   that account. Tenant isolation is enforced through ClientScopeManager.

4. No lifecycle (no validate/reject/edit)
   Only INSERT (archive) and UPDATE (unarchive) — DELETE is not exposed
   so the audit trail of past archivals is preserved.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager

from ..constants import SignalClusterType


class SignalClusterArchival(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Archival flag for a signal cluster identified by
    (account, signal_type, canonical_key) within a tenant.

    Semantics:
      - A cluster is considered archived when an active archival row
        exists, i.e. unarchived_at IS NULL.
      - Unarchiving sets unarchived_at to timezone.now() instead of
        deleting the row. This preserves the audit trail.
      - Re-archiving a previously unarchived cluster requires INSERTing
        a new row — the conditional unique constraint only covers rows
        where unarchived_at IS NULL, so multiple historical rows with
        unarchived_at set can coexist for the same cluster.
    """

    # =========================================================================
    # SCOPE — account
    # =========================================================================

    account = models.ForeignKey(
        'module_accounts.CompanyAccount',
        on_delete=models.CASCADE,
        related_name='signal_cluster_archivals',
        verbose_name=_('Account'),
        help_text=_('Account whose cluster is archived.'),
    )

    # =========================================================================
    # CLUSTER IDENTITY
    # =========================================================================

    signal_type = models.CharField(
        max_length=20,
        choices=SignalClusterType.choices,
        verbose_name=_('Signal Type'),
        help_text=_(
            "Signal family the cluster belongs to (e.g. 'pain'). "
            "Matches the type identifiers used by SignalDataService and "
            "the cluster endpoints."
        ),
    )

    canonical_key = models.CharField(
        max_length=255,
        verbose_name=_('Canonical Key'),
        help_text=_(
            "Stable cluster identifier — same value as BaseSignal.canonical_key "
            "on every member signal (e.g. 'pain:OPS:TIME')."
        ),
    )

    # =========================================================================
    # ARCHIVAL TRACKING
    # =========================================================================

    archived_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='signal_cluster_archivals',
        null=True,
        blank=True,
        verbose_name=_('Archived By'),
        help_text=_('User who archived the cluster.'),
    )

    unarchived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Unarchived At'),
        help_text=_(
            'Set when the cluster is unarchived. NULL means the cluster '
            'is currently archived. Kept for audit — never deleted.'
        ),
    )

    unarchived_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='signal_cluster_unarchivals',
        null=True,
        blank=True,
        verbose_name=_('Unarchived By'),
        help_text=_('User who unarchived the cluster (null while archived).'),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_cluster_archival'
        verbose_name = _('Signal Cluster Archival')
        verbose_name_plural = _('Signal Cluster Archivals')
        ordering = ['-created_at']

        indexes = [
            # Primary lookup path: "list clusters of account X, signal type
            # pain" → fetch archived canonical_keys in one shot.
            models.Index(
                fields=['account', 'signal_type', 'canonical_key'],
                name='sigclusarch_account_key_idx',
            ),
            # Faster filtering of currently-archived rows.
            models.Index(
                fields=['unarchived_at'],
                name='sigclusarch_unarchived_at_idx',
            ),
        ]

        constraints = [
            # A cluster has at most ONE active archival row at a time.
            # Once unarchived (unarchived_at IS NOT NULL), the row becomes
            # historical and a new INSERT is allowed to re-archive.
            models.UniqueConstraint(
                fields=['client_id', 'account', 'signal_type', 'canonical_key'],
                condition=models.Q(unarchived_at__isnull=True),
                name='sigclusarch_unique_active',
            ),
        ]

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        state = 'archived' if self.unarchived_at is None else 'unarchived'
        return (
            f"SignalClusterArchival | "
            f"{self.signal_type}:{self.canonical_key} | "
            f"account={self.account_id} | {state}"
        )