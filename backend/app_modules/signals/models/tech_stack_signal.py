# backend/app_modules/signals/models/tech_stack_signal.py
"""
TechStackSignal — concrete signal for technology stack data.

Captures structured intelligence about tools used by the account.
One signal = one facet (field_name) of one tool (tech_name) on one account.

tech_name holds the tool name as mentioned in the transcript.
It may not match any existing entity — that is intentional.
There is no FK to a TechStack table in app_modules.

field_name is constrained to TechStackField choices.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import TechStackField


class TechStackSignal(BaseSignal):
    """
    Concrete signal for technology stack data.

    Inherits all fields from BaseSignal and adds:
      - tech_name  : tool name as mentioned in the transcript (free text)
      - field_name : constrained to TechStackField choices

    No FK to a TechStack entity — the tool is identified by tech_name only.
    Matching to a canonical entity, if needed, is a concern for a later sprint.
    """

    field_name = models.CharField(
        max_length=50,
        choices=TechStackField.choices,
        verbose_name=_('Tech Stack Field'),
        help_text=_(
            'Identifies which facet of the tool this signal captures '
            '(purpose, pros, cons, costs, renewal date, or start year).'
        )
    )

    tech_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Tech Name'),
        help_text=_(
            'Name of the tool as mentioned in the transcript. '
            'Free text — may not match a canonical entity. '
            'Empty when the tool name was not identifiable.'
        )
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['field_name'],
    )):
        db_table = 'module_signals_tech_stack'
        verbose_name = _('Tech Stack Signal')
        verbose_name_plural = _('Tech Stack Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'],           name='tsig_account_idx'),
            models.Index(fields=['status'],            name='tsig_status_idx'),
            models.Index(fields=['signal_category'],   name='tsig_category_idx'),
            models.Index(fields=['source_department'], name='tsig_department_idx'),
            models.Index(fields=['source'],            name='tsig_source_idx'),
        ]

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        tool = self.tech_name or 'Unknown tool'
        return (
            f"TechStackSignal | "
            f"{tool} | "
            f"{self.get_field_name_display()} | "
            f"{self.get_status_display()}"
        )