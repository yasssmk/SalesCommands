# backend/app_modules/signals/models/qualification_signal.py
"""
QualificationSignal — concrete signal for commercial qualification data.

Captures structured sales intelligence across five groups:
  PEOPLE        — stakeholder mapping (decision maker, champion, blocker…)
  PAINS         — pain analysis chain (origin → impact → consequence → cost…)
  SITUATION     — current state (tools, process, integrations, limitations…)
  PAPER PROCESS — buying mechanics (criteria, process, timeline, deal risk…)
  PROFILE       — company sizing (company_size, annual_revenue)

field_name is constrained to QualificationField choices.
No extra model fields beyond BaseSignal — the field_name choice set
is the only concrete addition.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import QualificationField


class QualificationSignal(BaseSignal):
    """
    Concrete signal for qualification data.

    One signal = one data point for one field_name on one account.
    Multiple signals for the same field_name are allowed and represent
    different sources, contacts, or moments in time.

    Inherits all fields from BaseSignal.
    The only concrete addition is constraining field_name to
    QualificationField choices.
    """

    field_name = models.CharField(
        max_length=50,
        choices=QualificationField.choices,
        verbose_name=_('Qualification Field'),
        help_text=_(
            'Identifies which qualification dimension this signal captures. '
            'Must be one of the QualificationField choices.'
        )
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['field_name'],
    )):
        db_table = 'module_signals_qualification'
        verbose_name = _('Qualification Signal')
        verbose_name_plural = _('Qualification Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'],            name='qsig_account_idx'),
            models.Index(fields=['status'],             name='qsig_status_idx'),
            models.Index(fields=['signal_category'],    name='qsig_category_idx'),
            models.Index(fields=['source_department'],  name='qsig_department_idx'),
            models.Index(fields=['source'],             name='qsig_source_idx'),
        ]

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"QualificationSignal | "
            f"{self.get_field_name_display()} | "
            f"{self.get_status_display()}"
        )