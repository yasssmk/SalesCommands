# app_modules/signals/models/tech_stack_signal.py
"""
TechStackSignal — concrete signal for tools used by an account.

Captures structured intelligence about a single tool observed at an
account, anchored to a tenant-level master catalog entry (TechCatalog).
The catalog FK is the cluster identity: every observation of the same
tool on the same account aggregates into a single cluster, regardless
of who reported it or when.

Canonical key (auto-computed in save()):
    canonical_key = "techstack:<tech_catalog_entry.id>"

Because TechCatalog is tenant-level and the FK is scoped accordingly,
the canonical_key is automatically tenant-deduplicated — no risk of
two tenants producing colliding keys for distinct catalog entries.

Architectural alignment with Pain / Objective
---------------------------------------------
TechStackSignal follows the same canonical-cluster pattern as Pain and
Objective:

  * Inherits from BaseSignal (shared lifecycle, audit, source tracking).
  * canonical_key is auto-computed in save() before delegating to
    BaseSignal.save() which applies the MANUAL → VALIDATED rule.
  * Conditional validation lives in clean() and is mirrored by the
    Create / Update serializers (merged-state pattern as on
    ObjectiveSignal / ImpactSignal).
  * Cluster aggregation is delegated entirely to SignalClusterService
    via the shared dispatch — see _list_techstack_clusters_for_account.

Shadow-overrides (vs BaseSignal)
--------------------------------
TechStackSignal narrows the BaseSignal field set by shadow-overriding
two inherited fields to `None`. Each override has a precise reason:

  * decision_cycle — RESTORED (no longer shadow-overridden).
        A TechStack with decision_cycle=NULL represents a tool in place
        at the account level (incumbent). A TechStack with a non-null
        decision_cycle represents a tool being evaluated on that
        specific deal (competitor in play). The distinction is driven
        by the DC Workspace competitor model.

  * campaign = None
        Same logic — a campaign targets accounts, not their internal
        tooling. Inferable from source_activity.campaign on read when
        needed.

  * signal_category = None
        Aligned with ObjectiveSignal. The signal_category tag is not
        meaningful for TechStack observations — categorisation lives
        on the TechCatalog entry instead via the is_competitor and
        is_integration_target flags.

History — fields removed from BaseSignal directly:
  source_contact and source_department were previously shadow-overridden
  here as well. They have been removed from BaseSignal abstract during
  the standardisation refactor — contacts associated with a TechStack
  observation are now uniformly derived from source_activity.contacts
  through the standardised `source` block in serializers (see
  SignalSourceMixin in base_serializer.py). The shadow-override
  declarations are therefore obsolete and have been removed.

The MUST-keep inherited fields are: account, source_activity (optional),
canonical_key, source_quote, source, status, validated_*, audit
(created_by / updated_by / etc.), language_original, requested_by,
metadata, is_inferred, confidence, original_value.


Validation rules (enforced in clean() AND in Create/Update serializers)
----------------------------------------------------------------------
  1. source_activity is required — every TechStack observation must be
     tied to a real conversation. The DB column is also NOT NULL,
     guaranteeing the rule at every layer. Raising in clean() yields
     a clean ValidationError on the API surface rather than an
     IntegrityError.

  2. tech_catalog_entry is required, EXCEPT on PENDING LLM-extracted
     signals.
       Without the catalog FK, the canonical_key cannot be computed
       and cluster aggregation falls apart. The exception covers the
       LLM-extraction case where the mentioned tool could not be
       matched to the tenant catalog: the signal is persisted as
       PENDING with tech_catalog_entry=NULL and the raw name stored
       in metadata['pending_tech_name']. The rep must attach a
       catalog entry (or create one) before validating — enforced
       downstream by SignalManager.validate(). Any other source/
       status combination still requires the FK at clean() time.

  3. usage_scope = DEPARTMENT  →  usage_department REQUIRED.
     usage_scope ∈ {TEAM, COMPANY, UNKNOWN, None}  →  usage_department
                                                       FORBIDDEN.

  4. is_discontinued = True  →  discontinued_date REQUIRED.
     is_discontinued = False (default)  →  discontinued_date FORBIDDEN.

The (3) and (4) pairs use the merged-state validation pattern in their
matching serializers — see TechStackSignalUpdateSerializer.

Status creation rule
--------------------
TechStackSignal does not override BaseSignal.save()'s source-driven
status logic:

  * source = MANUAL              → status forced to VALIDATED
  * source = LLM_EXTRACTED       → status starts PENDING
  * source = LLM_MODIFIED        → status starts PENDING
  * source = EXTERNAL_RESEARCH   → status starts PENDING (rep validates)

This matches the rule already in effect across Pain and Objective —
no divergence introduced by this sprint.

Multi-mentions are expected
---------------------------
There is intentionally NO UniqueConstraint on (account, tech_catalog_entry).
Multiple signals for the same tool on the same account are the corroboration
mechanism: each call where Salesforce comes up adds one signal, and the
cluster service rolls them up. Mirror of the Pain/Objective stance.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager
from core.error_messages import SignalErrorMessages

from .base_model import BaseSignal
from ..constants import UsageScope, SignalSource, SignalStatus


class TechStackSignal(BaseSignal):
    """
    Concrete signal for a tool used by an account.

    Cluster identity:
        canonical_key = "techstack:<tech_catalog_entry.id>"
        — auto-computed in save() from the catalog FK.

    Required:
        - tech_catalog_entry (FK TechCatalog)

    Conditional:
        - usage_department  (required iff usage_scope == DEPARTMENT)
        - discontinued_date (required iff is_discontinued is True)

    Optional:
        - usage_scope, usage_start_year, renewal_date, cost_description, notes

    Source contacts:
        Contacts who participated in `source_activity` are derived at
        read time from `source_activity.contacts` and exposed through
        the standardised `source` block in serializers. The signal does
        not carry a dedicated source_contact FK — see BaseSignal class
        docstring for the rationale. usage_department is a distinct
        concept that captures who USES the tool, not who reported it.

    Inherited from BaseSignal (kept):
        - account, source_activity (nullable), source_quote, source,
          status, validated_*, language_original, requested_by, metadata,
          is_inferred, confidence, original_value, canonical_key, audit fields.
    """

    # =========================================================================
    # SHADOW OVERRIDES — narrow the BaseSignal field set
    # =========================================================================
    # See module docstring for the rationale of each override.
    # decision_cycle is no longer overridden — it is inherited from
    # BaseSignal to support the account-level vs deal-level distinction.
    campaign          = None
    signal_category   = None

    # =========================================================================
    # CATALOG ANCHOR (required — drives canonical_key)
    # =========================================================================

    tech_catalog_entry = models.ForeignKey(
        'tech_catalog.TechCatalog',
        on_delete=models.PROTECT,
        related_name='tech_stack_signals',
        null=True,
        blank=True,
        verbose_name=_('Tech Catalog Entry'),
        help_text=_(
            'Tenant-level master catalog entry identifying the tool. '
            'Drives canonical_key and cluster identity. '
            'Required for MANUAL signals and required to validate any '
            'signal. May be NULL on PENDING LLM-extracted signals when '
            'the LLM could not match the mentioned tool to the catalog '
            '— the rep must attach a catalog entry (or create one) '
            'before validating. PROTECT semantics apply only when the '
            'FK is set.'
        ),
    )
    # Note on on_delete=PROTECT: deleting a catalog entry that has live
    # signals would silently amputate the corroboration chain. PROTECT
    # forces the admin to handle migration (re-point or archive) before
    # removing the entry. Same stance as PainSignal.account (CASCADE is
    # appropriate when the parent OWNS the children; here the catalog
    # is a reference, not an owner — PROTECT is the right semantic).

    # =========================================================================
    # USAGE SCOPE (optional — drives conditional usage_department)
    # =========================================================================

    usage_scope = models.CharField(
        max_length=20,
        choices=UsageScope.choices,
        null=True,
        blank=True,
        verbose_name=_('Usage Scope'),
        help_text=_(
            'Organisational scope of the tool usage at this account. '
            'When DEPARTMENT, usage_department must be set. '
            'When TEAM / COMPANY / UNKNOWN, usage_department must be null.'
        ),
    )

    usage_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='tech_stack_signals_using',
        null=True,
        blank=True,
        verbose_name=_('Usage Department'),
        help_text=_(
            'Department using this tool — required when usage_scope=DEPARTMENT, '
            'forbidden otherwise. Distinct from any inherited "source" '
            'department (which describes who mentioned the tool, not who '
            'uses it — and is shadow-overridden away on this signal).'
        ),
    )

    # =========================================================================
    # LIFECYCLE STATS (optional — feed cluster all_observations)
    # =========================================================================

    usage_start_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Usage Start Year'),
        help_text=_(
            'Year the account started using this tool, when mentioned '
            '(e.g. 2019). Aggregated by the cluster service to expose '
            'the earliest observed start year across all observations.'
        ),
    )

    renewal_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Renewal Date'),
        help_text=_(
            'Next contract renewal date for this tool, when mentioned. '
            'The cluster service exposes the most recent observation '
            'and surfaces an urgency flag when within '
            'TECHSTACK_RENEWAL_SOON_DAYS from today.'
        ),
    )

    cost_description = models.TextField(
        blank=True,
        verbose_name=_('Cost Description'),
        help_text=_(
            'Free-text cost description as expressed during the conversation '
            '(e.g. "around 3000€/month", "120k$/year", "free tier"). '
            'Intentionally NOT a structured numeric field — costs are reported '
            'with widely varying granularity and currency by reps; structured '
            'capture would lose nuance and force false precision.'
        ),
    )

    # =========================================================================
    # DISCONTINUATION
    # =========================================================================

    is_discontinued = models.BooleanField(
        default=False,
        verbose_name=_('Is Discontinued'),
        help_text=_(
            'True when the account has stopped using or plans to stop using '
            'this tool. Drives the conditional discontinued_date requirement '
            'and a strong negative weight in cluster priority scoring '
            '(a discontinued tool is a closed door, not an open one).'
        ),
    )

    discontinued_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Discontinued Date'),
        help_text=_(
            'Date of discontinuation — required when is_discontinued is True, '
            'forbidden otherwise. Past dates indicate already-stopped usage; '
            'future dates indicate a planned phase-out.'
        ),
    )

    # =========================================================================
    # NOTES
    # =========================================================================

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional qualitative context about this observation.'),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_tech_stack'
        verbose_name = _('Tech Stack Signal')
        verbose_name_plural = _('Tech Stack Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['account'],
                name='tssig_account_idx',
            ),
            models.Index(
                fields=['tech_catalog_entry'],
                name='tssig_catalog_idx',
            ),
            models.Index(
                fields=['status'],
                name='tssig_status_idx',
            ),
            models.Index(
                fields=['is_discontinued'],
                name='tssig_discontinued_idx',
            ),
            # Composite index for the cluster lookup path:
            # "list TechStack clusters for account X" iterates by
            # account then groups by canonical_key.
            models.Index(
                fields=['account', 'canonical_key'],
                name='tssig_account_canon_idx',
            ),
            # Renewal-date ordering surface — supports the priority
            # scorer's renewal-soon detection on cluster aggregation.
            models.Index(
                fields=['renewal_date'],
                name='tssig_renewal_idx',
            ),
        ]

    # =========================================================================
    # SAVE — canonical_key auto-computation
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Compute canonical_key before delegating to BaseSignal.save().

        canonical_key = "techstack:<tech_catalog_entry.id>"

        The catalog FK is required at clean() time, but save() may run
        on a partially constructed instance during creation flows — we
        guard the assignment so that a missing FK leaves canonical_key
        as None rather than raising. The DB-level NOT NULL on
        tech_catalog_entry will catch the missing FK regardless.

        BaseSignal.save() then applies the shared business rules
        (MANUAL → VALIDATED + confidence cleared).
        """
        if self.tech_catalog_entry_id:
            self.canonical_key = f"techstack:{self.tech_catalog_entry_id}"
        else:
            self.canonical_key = None

        super().save(*args, **kwargs)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce TechStackSignal-specific constraints.

        Rules (all errors aggregated, returned as a single ValidationError):

          1. source_activity is required — every TechStack observation
             must be tied to a real conversation. The DB column is also
             NOT NULL. Raising in clean() yields a clean error payload
             on the API surface rather than an IntegrityError on save.

          2. tech_catalog_entry is required — the catalog FK drives
             canonical_key. The DB-level NOT NULL would catch this at
             save() time, but raising in clean() yields a clean error
             payload and matches the Pain/Objective pattern.

             Exception: LLM extraction may produce a signal whose
             mentioned tool does not match the tenant TechCatalog. In
             that case the signal is persisted as PENDING with
             tech_catalog_entry=None and the raw name stored in
             metadata['pending_tech_name']. The rep must attach a
             catalog entry before validating — enforced downstream by
             SignalManager.validate().

          3. usage_scope = DEPARTMENT
                → usage_department REQUIRED.
             usage_scope ∈ {TEAM, COMPANY, UNKNOWN, None}
                → usage_department FORBIDDEN.

          4. is_discontinued = True
                → discontinued_date REQUIRED.
             is_discontinued = False (default)
                → discontinued_date FORBIDDEN.

        Note on rule 3 with usage_scope = None:
          A null usage_scope is interpreted as "scope not yet
          documented". Setting usage_department in that state would
          create an inconsistent record (a department is set but no
          scope justifies it). Forbidden.
        """
        super().clean()

        errors = {}

        # --- Rule 1: source_activity required ---
        if not self.source_activity_id:
            errors['source_activity'] = (
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        # --- Rule 2: catalog FK is required EXCEPT on PENDING LLM-extracted signals ---
        # LLM extraction may produce a signal whose mentioned tool does
        # not match the tenant TechCatalog (the prompt feeds the catalog
        # list and instructs the model to return a raw tech_name when
        # no match exists). In that case the signal is persisted as
        # PENDING with tech_catalog_entry=None and the raw name stored
        # in metadata['pending_tech_name']. The rep must attach a
        # catalog entry before validating — enforced downstream by
        # SignalManager.validate().
        if not self.tech_catalog_entry_id:
            is_unmatched_llm_pending = (
                self.source == SignalSource.LLM_EXTRACTED
                and self.status == SignalStatus.PENDING
            )
            if not is_unmatched_llm_pending:
                errors['tech_catalog_entry'] = (
                    SignalErrorMessages.TECHSTACK_CATALOG_ENTRY_REQUIRED
                )

        # --- Rule 3: usage_scope ↔ usage_department coherence ---
        if self.usage_scope == UsageScope.DEPARTMENT:
            if not self.usage_department_id:
                errors['usage_department'] = (
                    SignalErrorMessages.TECHSTACK_DEPT_REQUIRES_DEPT
                )
        else:
            # Covers TEAM, COMPANY, UNKNOWN, and None.
            if self.usage_department_id:
                errors['usage_department'] = (
                    SignalErrorMessages.TECHSTACK_DEPT_OUTSIDE_SCOPE
                )

        # --- Rule 4: is_discontinued ↔ discontinued_date coherence ---
        if self.is_discontinued:
            if not self.discontinued_date:
                errors['discontinued_date'] = (
                    SignalErrorMessages.TECHSTACK_DISCONTINUED_REQUIRES_DATE
                )
        else:
            if self.discontinued_date:
                errors['discontinued_date'] = (
                    SignalErrorMessages.TECHSTACK_DISCONTINUED_DATE_WITHOUT_FLAG
                )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        # Avoid an extra DB hit when the FK isn't loaded — fall back to
        # the bare ID string instead of forcing a join just for repr.
        if self.tech_catalog_entry_id:
            try:
                tool = str(self.tech_catalog_entry)
            except Exception:
                tool = f"catalog:{self.tech_catalog_entry_id}"
        else:
            tool = 'no-catalog-entry'
        return (
            f"TechStackSignal | "
            f"{tool} | "
            f"{self.get_status_display()}"
        )