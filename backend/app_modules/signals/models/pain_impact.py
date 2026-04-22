# app_modules/signals/models/pain_impact.py
"""
PainImpact — tangible proof or human manifestation of a Pain.

Pain   = the DIAGNOSIS (qualitative, narrative)
Impact = the PROOF    (quantitative and/or human)

Each PainImpact is anchored to a PainSignal (FK, required).
The Pain dictates the canonical identity (via Pain.canonical_key);
the Impact carries the concrete evidence.

A PainSignal can have 0..N PainImpacts — a Pain can exist without
any documented proof yet, and can accumulate Impacts over time as the
AE gathers evidence across calls.

Three mutually-exclusive Impact levels, answering different sales
questions:

  BUSINESS   — "How much does it cost the company overall?"
               Champs caractéristiques: metric + notes.
               CFO-level evidence.

  DEPARTMENT — "Which department pays the price of this pain?"
               Champs caractéristiques: impacted_department + metric + notes.
               VP / team-lead evidence.

  PERSONAL   — "Who is personally bearing this pain?"
               Champs caractéristiques: impacted_contact + metric (optional)
               + human_impact (optional) + notes.
               Champion-level evidence.

Validation rules (enforced in clean()):
  - level is required
  - BUSINESS impact: neither impacted_contact nor impacted_department set
  - DEPARTMENT impact: impacted_department required, impacted_contact must
    not be set
  - PERSONAL impact: impacted_contact required, impacted_department must
    not be set; human_impact remains optional
  - impacted_contact (when set) must belong to the parent Pain's account

Note — Lifecycle and source fields:
  PainImpact does NOT inherit from BaseSignal. It has no lifecycle of its
  own (no PENDING/VALIDATED/REJECTED), no source enum, no confidence, no
  corroboration. Its truth-value is tied to the parent Pain. It only
  tracks: client_id (multi-tenant), created_by / updated_by / timestamps
  (audit), and the business fields described above.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager

from ..constants import HumanImpact, ImpactLevel


class PainImpact(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Concrete proof or manifestation of a PainSignal.

    Schema summary:
      pain_signal       : FK to PainSignal (required, CASCADE)
      level             : ImpactLevel (BUSINESS / DEPARTMENT / PERSONAL)
      impacted_department : FK StandardDepartment (required if DEPARTMENT)
      impacted_contact    : FK Contact (required if PERSONAL)
      human_impact      : HumanImpact enum (optional, PERSONAL only)
      metric            : free text — e.g. "120k$/year", "15h/week"
      notes             : free text — additional qualitative context

    Inherits from ModuleBaseModel:
      id, client_id, created_by, updated_by, created_at, updated_at.

    No lifecycle (no status, source, confidence, validated_by) — these
    concepts belong to BaseSignal and are intentionally absent here.
    An Impact is truth-by-association: it is only meaningful attached to
    its parent Pain and rises/falls with it.
    """

    # =========================================================================
    # ANCHOR — parent Pain
    # =========================================================================

    pain_signal = models.ForeignKey(
        'module_signals.PainSignal',
        on_delete=models.CASCADE,
        related_name='impacts',
        verbose_name=_('Pain Signal'),
        help_text=_('The PainSignal this impact documents — required.')
    )

    # =========================================================================
    # LEVEL — drives conditional field requirements
    # =========================================================================

    level = models.CharField(
        max_length=20,
        choices=ImpactLevel.choices,
        verbose_name=_('Impact Level'),
        help_text=_(
            'The scope of this impact: BUSINESS (company-wide), '
            'DEPARTMENT (scoped to one department), or PERSONAL (scoped '
            'to one individual contact).'
        )
    )

    # =========================================================================
    # DEPARTMENT IMPACT — required when level = DEPARTMENT
    # =========================================================================

    impacted_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='pain_impacts',
        null=True,
        blank=True,
        verbose_name=_('Impacted Department'),
        help_text=_(
            'Department bearing this impact. Required when level=DEPARTMENT; '
            'must be null for BUSINESS and PERSONAL impacts.'
        )
    )

    # =========================================================================
    # PERSONAL IMPACT — required when level = PERSONAL
    # =========================================================================

    impacted_contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.SET_NULL,
        related_name='pain_impacts',
        null=True,
        blank=True,
        verbose_name=_('Impacted Contact'),
        help_text=_(
            'Contact personally experiencing this impact. Required when '
            'level=PERSONAL; must be null for BUSINESS and DEPARTMENT '
            'impacts. Must belong to the parent Pain\'s account.'
        )
    )

    human_impact = models.CharField(
        max_length=20,
        choices=HumanImpact.choices,
        blank=True,
        null=True,
        verbose_name=_('Human Impact'),
        help_text=_(
            'Personal consequence on the impacted contact — frustration, '
            'overload, stress, demotivation, conflict. Optional, and only '
            'meaningful on PERSONAL impacts.'
        )
    )

    # =========================================================================
    # SHARED CONTENT — metric + notes
    # =========================================================================

    metric = models.TextField(
        blank=True,
        verbose_name=_('Metric / Measurement'),
        help_text=_(
            'Quantified evidence of the impact as mentioned during the '
            'conversation. Free text — e.g. "120k$/year lost productivity", '
            '"15h/week wasted", "3h/week overtime". Optional.'
        )
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional qualitative context about this impact.')
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_pain_impact'
        verbose_name = _('Pain Impact')
        verbose_name_plural = _('Pain Impacts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pain_signal'],         name='painimp_pain_idx'),
            models.Index(fields=['level'],               name='painimp_level_idx'),
            models.Index(fields=['impacted_department'], name='painimp_dept_idx'),
            models.Index(fields=['impacted_contact'],    name='painimp_contact_idx'),
            models.Index(fields=['human_impact'],        name='painimp_human_idx'),
        ]
        constraints = [
            # A contact can bear at most one PainImpact per PainSignal.
            # Avoids the noise of duplicate "Marie is OVERLOAD" entries on
            # the same pain. If richer tracking is needed (multiple impact
            # types per contact per pain), this constraint can be relaxed
            # later.
            models.UniqueConstraint(
                fields=['pain_signal', 'impacted_contact'],
                condition=models.Q(impacted_contact__isnull=False),
                name='painimp_unique_pain_contact',
            ),
        ]

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce ImpactLevel-based conditional requirements and cross-account
        scoping.

        Rules:
          1. level is required (enforced at schema level too).
          2. BUSINESS  → impacted_department and impacted_contact must both be
             null. human_impact must also be null (not meaningful at
             business scope).
          3. DEPARTMENT → impacted_department required; impacted_contact
             must be null; human_impact must be null.
          4. PERSONAL  → impacted_contact required; impacted_department
             must be null; human_impact is optional.
          5. impacted_contact (when set) must belong to the parent Pain's
             account.
        """
        super().clean()

        errors = {}

        # Rule 1 — level is required. Schema NOT NULL also enforces it, but
        # we surface a friendly error here for form submissions.
        if not self.level:
            errors['level'] = _('Impact level is required.')
            raise ValidationError(errors)

        # Rules 2-4 — level-driven field presence
        if self.level == ImpactLevel.BUSINESS:
            if self.impacted_department_id:
                errors['impacted_department'] = _(
                    'Business impacts must not specify an impacted department.'
                )
            if self.impacted_contact_id:
                errors['impacted_contact'] = _(
                    'Business impacts must not specify an impacted contact.'
                )
            if self.human_impact:
                errors['human_impact'] = _(
                    'Human impact is only meaningful on personal impacts.'
                )

        elif self.level == ImpactLevel.DEPARTMENT:
            if not self.impacted_department_id:
                errors['impacted_department'] = _(
                    'Department impacts require an impacted department.'
                )
            if self.impacted_contact_id:
                errors['impacted_contact'] = _(
                    'Department impacts must not specify an impacted contact. '
                    'Use a personal impact instead.'
                )
            if self.human_impact:
                errors['human_impact'] = _(
                    'Human impact is only meaningful on personal impacts.'
                )

        elif self.level == ImpactLevel.PERSONAL:
            if not self.impacted_contact_id:
                errors['impacted_contact'] = _(
                    'Personal impacts require an impacted contact.'
                )
            if self.impacted_department_id:
                errors['impacted_department'] = _(
                    'Personal impacts must not specify an impacted department. '
                    'Use a department impact instead.'
                )
            # human_impact is optional for PERSONAL — no check here.

        # Rule 5 — cross-account scoping on impacted_contact.
        # We only enforce when both pain_signal and impacted_contact are
        # resolvable — they may not be fully loaded during partial
        # construction in serializers.
        if (
            self.impacted_contact_id
            and self.pain_signal_id
            and hasattr(self, 'impacted_contact') and self.impacted_contact
            and hasattr(self, 'pain_signal') and self.pain_signal
        ):
            pain_account = self.pain_signal.account_id
            contact_account = self.impacted_contact.account_id
            if str(pain_account) != str(contact_account):
                errors['impacted_contact'] = _(
                    'Impacted contact must belong to the same account as '
                    'the parent pain.'
                )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        if self.level == ImpactLevel.BUSINESS:
            target = 'Business-wide'
        elif self.level == ImpactLevel.DEPARTMENT:
            target = (
                f"Dept {self.impacted_department_id}"
                if self.impacted_department_id else 'Dept (unset)'
            )
        elif self.level == ImpactLevel.PERSONAL:
            target = (
                f"Contact {self.impacted_contact_id}"
                if self.impacted_contact_id else 'Contact (unset)'
            )
        else:
            target = 'Unknown level'

        return (
            f"PainImpact | Pain {self.pain_signal_id} | "
            f"{self.get_level_display()} | {target}"
        )