# app_modules/signals/models/tech_stack_signal.py
"""
TechStackSignal — concrete signal for tools used by an account.

Captures structured intelligence about a single tool observed at an
account. The tool is identified by free text: `tech_name` holds the
name as it was observed, and `tech_name_normalized` (derived in save())
is the key used to group, filter and de-duplicate observations.

TechStack is NOT clusterable (product decision). Unlike Pain /
Objective / Impact, TechStack observations are not aggregated into
canonical clusters — the signal carries no canonical_key and is not
served by SignalClusterService. Multiple observations of the same
tool on an account are read as a flat list, grouped on the normalised
name.

Architectural alignment with Pain / Objective
---------------------------------------------
TechStackSignal shares the BaseSignal lifecycle but, unlike Pain /
Objective / Impact, does not participate in cluster aggregation:

  * Inherits from BaseSignal (shared lifecycle, audit, source tracking).
  * Does not compute a canonical_key — TechStack is not clusterable.
  * Conditional validation lives in clean() and is mirrored by the
    Create / Update serializers (merged-state pattern as on
    ObjectiveSignal / ImpactSignal).

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
        meaningful for TechStack observations — qualification lives on
        the signal itself via the is_competitor / is_integration /
        is_to_replace flags.

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

  2. usage_scope = DEPARTMENT  →  usage_department REQUIRED.
     usage_scope ∈ {TEAM, COMPANY, UNKNOWN, None}  →  usage_department
                                                       FORBIDDEN.

  3. is_discontinued = True  →  discontinued_date REQUIRED.
     is_discontinued = False (default)  →  discontinued_date FORBIDDEN.

The (2) and (3) pairs use the merged-state validation pattern in their
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
There is intentionally NO UniqueConstraint on
(account, tech_name_normalized). Multiple signals for the same tool on the
same account are the corroboration mechanism: each call where Salesforce
comes up adds one signal. They are read as a flat list grouped on the
normalised name (TechStack is not clustered).
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager
from core.error_messages import SignalErrorMessages

from .base_model import BaseSignal
from ..constants import UsageScope


class TechStackSignal(BaseSignal):
    """
    Concrete signal for a tool used by an account.

    Tech identity:
        tech_name             raw display text, as written ("Salesforce CRM").
        tech_name_normalized  derived in save() (lower + trim + collapse);
                              the grouping / filtering / de-dup key.
        tech_name is the single source of truth — the normalised column
        is recomputed on every write and can never desync from it.

    Qualification flags (independent, default False):
        is_competitor, is_integration, is_to_replace. All three False
        means "a tool the account simply uses".

    Not clusterable — no canonical_key is computed.

    Required:
        - tech_name (the tool's identity; blank names carry no meaning)

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
    # TECH IDENTITY (raw + derived normalised key)
    # =========================================================================
    #
    # `tech_name` is the single source of truth for the tool's identity.
    # `tech_name_normalized` is DERIVED from it in save() and must never
    # be authored by a caller — see the SAVE section below.
    #
    # Both are non-nullable free text defaulting to '' — the prevailing
    # convention for free-text columns on this model (cf.
    # `cost_description` and `notes` further down, which declare
    # `blank=True` and rely on Django's implicit '' default). Only
    # `usage_scope` uses null=True, because "scope not documented" is a
    # meaningful third state there; "no tech name" is simply the empty
    # string.

    tech_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Tech Name'),
        help_text=_(
            'Raw display name of the tool exactly as it was written by '
            'the LLM or the rep (e.g. "Salesforce CRM"). Never rewritten '
            '— casing, spacing and wording are preserved for display. '
            'Grouping, filtering and de-duplication use '
            '`tech_name_normalized` instead.'
        ),
    )

    tech_name_normalized = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Tech Name (normalised)'),
        help_text=_(
            'Derived from `tech_name` on every save: lowercased, '
            'trimmed, internal whitespace collapsed to single spaces. '
            'This is the key used to group, filter and de-duplicate '
            'observations of the same tool. Read-only by contract — it '
            'is recomputed at save() time, so any value written by a '
            'caller is discarded and the two columns cannot desync. '
            'Empty string when `tech_name` is blank.'
        ),
    )

    # =========================================================================
    # QUALIFICATION FLAGS
    # =========================================================================
    #
    # Three INDEPENDENT booleans — a single tool can be several of these
    # at once (a competitor we also integrate with and want to replace),
    # or none. All three False is the default and the common case: a
    # tool the account simply uses.
    #
    # Declared in the style of `is_discontinued` below (BooleanField,
    # default=False, verbose_name + help_text).

    is_competitor = models.BooleanField(
        default=False,
        verbose_name=_('Is Competitor'),
        help_text=_(
            'True when this tool overlaps with what we sell — '
            'displacing it is a winnable angle on the deal.'
        ),
    )

    is_integration = models.BooleanField(
        default=False,
        verbose_name=_('Is Integration'),
        help_text=_(
            'True when this tool is one we connect to — integrating '
            'with it is a winnable angle on the deal.'
        ),
    )

    is_to_replace = models.BooleanField(
        default=False,
        verbose_name=_('Is To Replace'),
        help_text=_(
            'True when the account intends to replace this tool — an '
            'open door regardless of whether we compete with it or '
            'integrate with it.'
        ),
    )

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
                fields=['status'],
                name='tssig_status_idx',
            ),
            models.Index(
                fields=['is_discontinued'],
                name='tssig_discontinued_idx',
            ),
            # Renewal-date ordering surface for the account tech-stack list.
            models.Index(
                fields=['renewal_date'],
                name='tssig_renewal_idx',
            ),
            # Grouping / filtering surface for "which accounts use tool X"
            # and for de-duplicating repeated observations of one tool.
            # Declared here rather than via db_index=True on the field so
            # every index on this model stays visible in one block, and
            # so the name is explicit (same stance as the five above).
            models.Index(
                fields=['tech_name_normalized'],
                name='tssig_tech_norm_idx',
            ),
        ]

    # =========================================================================
    # SAVE — derive tech_name_normalized from tech_name
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Recompute `tech_name_normalized` from `tech_name`, then delegate
        to BaseSignal.save().

        Signature mirrors the other concrete signal overrides —
        ImpactSignal.save() (models/impact_signal.py) and
        BlockerSignal.save() (models/blocker_signal.py) both declare
        `save(self, *args, **kwargs)` and forward untouched. `user` and
        `client_id` travel as kwargs and are popped further down the
        chain by ModuleBaseModel.save()
        (app_modules/core_modules/models/moduleBaseModels.py:71-98), so
        no override in this hierarchy names them explicitly.

        This is the single normalisation point by design: every write
        path — the transcript pipeline (SignalManager.create), the REST
        API (BaseSignalViewSet), a management command or a shell session
        — goes through Model.save(), so none of them can produce a row
        whose normalised key disagrees with its raw name.

        Rule: lowercase, strip, and collapse every run of internal
        whitespace (spaces, tabs, newlines) to a single space. Nothing
        smarter — no synonym table, no canonical_key. A blank or missing
        `tech_name` yields '' (not None).

        canonical_key is deliberately NOT touched here. TechStack is not
        clusterable; unlike BlockerSignal.save(), which force-nulls the
        column, this override leaves it exactly as the caller left it so
        that the field's cleanup stays a separate, explicit change.
        """
        self.tech_name_normalized = self._normalize_tech_name(self.tech_name)

        super().save(*args, **kwargs)

    @staticmethod
    def _normalize_tech_name(value):
        """
        Lowercase + trim + collapse internal whitespace.

        "  Salesforce   CRM " -> "salesforce crm"
        None / "" / "   "     -> ""
        """
        if not value:
            return ''
        # str.split() with no argument splits on arbitrary runs of
        # whitespace AND drops the leading/trailing runs, so the join
        # covers strip + collapse in one pass.
        return ' '.join(str(value).lower().split())

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

          2. usage_scope = DEPARTMENT
                → usage_department REQUIRED.
             usage_scope ∈ {TEAM, COMPANY, UNKNOWN, None}
                → usage_department FORBIDDEN.

          3. is_discontinued = True
                → discontinued_date REQUIRED.
             is_discontinued = False (default)
                → discontinued_date FORBIDDEN.

        Note on `tech_name`:
          Identity is NOT enforced here. An LLM-extracted signal is
          dropped upstream when the model emits no name (see
          TranscriptSignalExtractor._build_techstack_data), and the
          Create serializer requires it on the API path. Adding a
          model-level rule would break the historical rows the S10
          migration leaves with an empty name.

        Note on rule 2 with usage_scope = None:
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

        # --- Rule 2: usage_scope ↔ usage_department coherence ---
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

        # --- Rule 3: is_discontinued ↔ discontinued_date coherence ---
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
        tool = self.tech_name or 'unnamed-tool'
        return (
            f"TechStackSignal | "
            f"{tool} | "
            f"{self.get_status_display()}"
        )