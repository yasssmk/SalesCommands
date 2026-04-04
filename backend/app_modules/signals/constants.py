# app_modules/signals/constants.py
"""
Constants for the Signals module.

Defines all TextChoices enums used across signal models:
- SignalStatus   : lifecycle states of a signal
- SignalSource   : how the signal was created
- SignalCategory : commercial category of the signal
- QualificationField : allowed field_name values for QualificationSignal
- TechStackField     : allowed field_name values for TechStackSignal
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# =============================================================================
# SIGNAL STATUS
# =============================================================================

class SignalStatus(models.TextChoices):
    """
    Lifecycle states for all signal types.

    PENDING   — created by LLM extraction, awaiting rep validation
    VALIDATED — approved by the rep (or created manually)
    REJECTED  — dismissed by the rep, kept for audit trail
    MERGED    — absorbed into another signal via merge operation;
                merged_into FK points to the surviving signal
    """
    PENDING   = 'PENDING',   _('Pending')
    VALIDATED = 'VALIDATED', _('Validated')
    REJECTED  = 'REJECTED',  _('Rejected')
    MERGED    = 'MERGED',    _('Merged')


# =============================================================================
# SIGNAL SOURCE
# =============================================================================

class SignalSource(models.TextChoices):
    """
    Origin of a signal, used to drive auto-validation logic in save().

    MANUAL        — entered directly by the rep → status forced to VALIDATED
    LLM_EXTRACTED — extracted from transcript by LLM → status starts PENDING
    LLM_MODIFIED  — extracted by LLM then edited by rep before validation
    """
    MANUAL        = 'MANUAL',        _('Manual entry')
    LLM_EXTRACTED = 'LLM_EXTRACTED', _('LLM extracted')
    LLM_MODIFIED  = 'LLM_MODIFIED',  _('LLM modified')


# =============================================================================
# SIGNAL CATEGORY
# =============================================================================

class SignalCategory(models.TextChoices):
    """
    High-level commercial category of the signal.
    Used to group and filter signals across types.

    ECONOMIC   — budget, costs, financial constraints
    TIME       — timeline, urgency, deadlines
    FRICTION   — blockers, risks, objections
    RISK       — deal risk, compliance, legal exposure
    STRATEGIC  — strategic fit, executive alignment
    PEOPLE     — stakeholders, roles, relationships
    PROCESS    — buying process, decision criteria, workflows
    """
    ECONOMIC  = 'ECONOMIC',  _('Economic')
    TIME      = 'TIME',      _('Time')
    FRICTION  = 'FRICTION',  _('Friction')
    RISK      = 'RISK',      _('Risk')
    STRATEGIC = 'STRATEGIC', _('Strategic')
    PEOPLE    = 'PEOPLE',    _('People')
    PROCESS   = 'PROCESS',   _('Process')


# =============================================================================
# QUALIFICATION FIELD
# =============================================================================

class QualificationField(models.TextChoices):
    """
    Controlled vocabulary for QualificationSignal.field_name.

    Grouped by commercial category for readability — grouping is
    documentary only; Django treats all choices equally.

    PEOPLE group — stakeholder mapping
    PAINS group  — pain analysis (origin → consequence → resolution)
    SITUATION group — current state / existing tools
    PAPER PROCESS group — buying mechanics and timeline
    PROFILE group — company-level sizing data
    """

    # --- PEOPLE ---
    DECISION_MAKER      = 'decision_maker',      _('Decision Maker')
    ECONOMIC_BUYER      = 'economic_buyer',       _('Economic Buyer')
    CHAMPION            = 'champion',             _('Champion')
    BLOCKER             = 'blocker',              _('Blocker')
    END_USER            = 'end_user',             _('End User')
    PROCUREMENT_CONTACT = 'procurement_contact',  _('Procurement Contact')
    INTERNAL_DYNAMICS   = 'internal_dynamics',    _('Internal Dynamics')

    # --- PAINS ---
    PAIN_POINT          = 'pain_point',           _('Pain Point')
    PAIN_ORIGIN         = 'pain_origin',          _('Pain Origin')
    PAIN_IMPACT         = 'pain_impact',          _('Pain Impact')
    PAIN_CONSEQUENCE    = 'pain_consequence',     _('Pain Consequence')
    PAIN_MEASUREMENT    = 'pain_measurement',     _('Pain Measurement')
    BUSINESS_COST       = 'business_cost',        _('Business Cost')
    PAIN_MATURITY       = 'pain_maturity',        _('Pain Maturity')
    EXISTING_INITIATIVE = 'existing_initiative',  _('Existing Initiative')
    RESOLUTION_VALUE    = 'resolution_value',     _('Resolution Value')

    # --- SITUATION ---
    CURRENT_TOOL          = 'current_tool',           _('Current Tool')
    CURRENT_PROCESS       = 'current_process',         _('Current Process')
    EXISTING_INTEGRATIONS = 'existing_integrations',   _('Existing Integrations')
    KNOWN_LIMITATIONS     = 'known_limitations',       _('Known Limitations')
    SATISFACTION_LEVEL    = 'satisfaction_level',      _('Satisfaction Level')
    WORKAROUND            = 'workaround',              _('Workaround')

    # --- PAPER PROCESS ---
    BUYING_STAKEHOLDERS = 'buying_stakeholders', _('Buying Stakeholders')
    DECISION_CRITERIA   = 'decision_criteria',   _('Decision Criteria')
    BUYING_PROCESS      = 'buying_process',      _('Buying Process')
    TIMELINE            = 'timeline',            _('Timeline')
    DEAL_RISK           = 'deal_risk',           _('Deal Risk')

    # --- PROFILE ---
    COMPANY_SIZE   = 'company_size',   _('Company Size')
    ANNUAL_REVENUE = 'annual_revenue', _('Annual Revenue')


# =============================================================================
# TECH STACK FIELD
# =============================================================================

class TechStackField(models.TextChoices):
    """
    Controlled vocabulary for TechStackSignal.field_name.

    Each value captures one facet of a tool used by the account.
    The tool name itself lives in TechStackSignal.tech_name or signal.value.
    """
    PURPOSE          = 'purpose',           _('Purpose')
    PROS             = 'pros',              _('Pros')
    CONS             = 'cons',              _('Cons')
    COSTS            = 'costs',             _('Costs')
    RENEWAL_DATE     = 'renewal_date',      _('Renewal Date')
    START_YEAR_OF_USAGE = 'start_year_of_usage', _('Start Year of Usage')