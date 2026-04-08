# app_modules/signals/constants.py
"""
Constants for the Signals module.

Defines all TextChoices enums used across signal models.

Lifecycle / cross-cutting:
  SignalStatus   — lifecycle states shared by all signal types
  SignalSource   — how / where a signal originated
  SignalCategory — high-level commercial category (optional tagging)

Model-specific:
  PeopleRole     — stakeholder role for PeopleSignal
  InfluenceLevel — stakeholder influence level for PeopleSignal
  PainCategory   — nature of the pain for PainSignal
  PainLevel      — organisational scope of the pain for PainSignal
  GoalLevel      — organisational scope of the objective for ObjectiveSignal
  TechCategory   — technology category for TechStackSignal
  Satisfaction   — satisfaction level for TechStackSignal

Removed vs. previous version:
  - SignalStatus.MERGED      (merge operation removed from the module)
  - QualificationField       (replaced by dedicated structured models)
  - TechStackField           (replaced by rich fields on TechStackSignal)
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# =============================================================================
# SIGNAL STATUS
# =============================================================================

class SignalStatus(models.TextChoices):
    """
    Lifecycle states shared by all signal types.

    PENDING   — created by LLM extraction, awaiting rep validation
    VALIDATED — approved by the rep (or created manually via MANUAL source)
    REJECTED  — dismissed by the rep; kept for audit trail, never deleted
    """
    PENDING   = 'PENDING',   _('Pending')
    VALIDATED = 'VALIDATED', _('Validated')
    REJECTED  = 'REJECTED',  _('Rejected')


# =============================================================================
# SIGNAL SOURCE
# =============================================================================

class SignalSource(models.TextChoices):
    """
    Origin of a signal.

    Used to drive auto-validation logic in BaseSignal.save() and to
    communicate provenance to the rep and to LLM prompts.

    MANUAL            — entered directly by the rep after a conversation
                        → status forced to VALIDATED by BaseSignal.save()
    LLM_EXTRACTED     — extracted from a transcript by LLM
                        → status starts PENDING, rep must validate
                        → may still carry a source_activity when the LLM
                           processed a known CRM activity transcript
    LLM_MODIFIED      — extracted by LLM then edited by the rep before
                        validation; original value preserved in original_value
    EXTERNAL_RESEARCH — sourced from outside a CRM conversation
                        (e.g. LinkedIn lookup, internet research, LLM analysis
                        of public data); source_activity will be null
    """
    MANUAL            = 'MANUAL',            _('Manual entry')
    LLM_EXTRACTED     = 'LLM_EXTRACTED',     _('LLM extracted')
    LLM_MODIFIED      = 'LLM_MODIFIED',      _('LLM modified')
    EXTERNAL_RESEARCH = 'EXTERNAL_RESEARCH', _('External research')


# =============================================================================
# SIGNAL CATEGORY
# =============================================================================

class SignalCategory(models.TextChoices):
    """
    High-level commercial category of the signal.

    Optional tag applied to any signal type for filtering and grouping.
    Does not drive any business logic — purely descriptive.

    ECONOMIC  — budget, costs, financial constraints
    TIME      — timeline, urgency, deadlines
    FRICTION  — blockers, risks, objections
    RISK      — deal risk, compliance, legal exposure
    STRATEGIC — strategic fit, executive alignment
    PEOPLE    — stakeholders, roles, relationships
    PROCESS   — buying process, decision criteria, workflows
    """
    ECONOMIC  = 'ECONOMIC',  _('Economic')
    TIME      = 'TIME',      _('Time')
    FRICTION  = 'FRICTION',  _('Friction')
    RISK      = 'RISK',      _('Risk')
    STRATEGIC = 'STRATEGIC', _('Strategic')
    PEOPLE    = 'PEOPLE',    _('People')
    PROCESS   = 'PROCESS',   _('Process')


# =============================================================================
# PEOPLE SIGNAL — enums
# =============================================================================

class PeopleRole(models.TextChoices):
    """
    Stakeholder role observed in a PeopleSignal.

    Represents the commercial or organisational role the target contact
    plays in the buying process at the account.

    DECISION_MAKER  — has formal authority to sign off the deal
    ECONOMIC_BUYER  — controls the budget (may differ from decision maker)
    CHAMPION        — internal advocate for the solution
    BLOCKER         — actively opposing or slowing the deal
    END_USER        — will use the product day-to-day
    PROCUREMENT     — owns the vendor / contract management process
    INFLUENCER      — shapes opinions without formal authority
    """
    DECISION_MAKER  = 'DECISION_MAKER',  _('Decision Maker')
    ECONOMIC_BUYER  = 'ECONOMIC_BUYER',  _('Economic Buyer')
    CHAMPION        = 'CHAMPION',        _('Champion')
    BLOCKER         = 'BLOCKER',         _('Blocker')
    END_USER        = 'END_USER',        _('End User')
    PROCUREMENT     = 'PROCUREMENT',     _('Procurement')
    INFLUENCER      = 'INFLUENCER',      _('Influencer')


class InfluenceLevel(models.TextChoices):
    """
    Perceived influence level of the stakeholder in PeopleSignal.

    Optional qualifier on top of PeopleRole to communicate how much
    weight this person carries in the buying decision.
    """
    HIGH   = 'HIGH',   _('High')
    MEDIUM = 'MEDIUM', _('Medium')
    LOW    = 'LOW',    _('Low')


# =============================================================================
# PAIN SIGNAL — enums
# =============================================================================

class PainCategory(models.TextChoices):
    """
    Nature of the pain described in a PainSignal.

    Categorises the type of problem the account is experiencing,
    independent of which department or level it affects.

    OPERATIONAL  — process inefficiency, execution bottlenecks
    FINANCIAL    — cost overruns, revenue loss, budget pressure
    STRATEGIC    — misalignment with goals, competitive gaps
    TECHNICAL    — system limitations, integration failures, debt
    COMPLIANCE   — regulatory, legal, security, or audit exposure
    OTHER        — pain that does not fit the above categories
    """
    OPERATIONAL = 'OPERATIONAL', _('Operational')
    FINANCIAL   = 'FINANCIAL',   _('Financial')
    STRATEGIC   = 'STRATEGIC',   _('Strategic')
    TECHNICAL   = 'TECHNICAL',   _('Technical')
    COMPLIANCE  = 'COMPLIANCE',  _('Compliance')
    OTHER       = 'OTHER',       _('Other')


class PainLevel(models.TextChoices):
    """
    Organisational scope of the pain in a PainSignal.

    Indicates who is affected by the pain — the whole company, a
    specific department, or an individual contact.

    BUSINESS   — company-wide impact
    DEPARTMENT — limited to one or more departments
    PERSONAL   — experienced primarily by one individual
    """
    BUSINESS   = 'BUSINESS',   _('Business')
    DEPARTMENT = 'DEPARTMENT', _('Department')
    PERSONAL   = 'PERSONAL',   _('Personal')


# =============================================================================
# OBJECTIVE SIGNAL — enums
# =============================================================================

class GoalLevel(models.TextChoices):
    """
    Organisational scope of the objective in an ObjectiveSignal.

    Mirrors PainLevel intentionally — both describe at which layer of the
    organisation the signal applies. Kept as a separate enum so they can
    evolve independently.

    BUSINESS   — company-wide strategic goal
    DEPARTMENT — departmental objective
    PERSONAL   — individual goal or KPI
    """
    BUSINESS   = 'BUSINESS',   _('Business')
    DEPARTMENT = 'DEPARTMENT', _('Department')
    PERSONAL   = 'PERSONAL',   _('Personal')


# =============================================================================
# TECH STACK SIGNAL — enums
# =============================================================================

class TechCategory(models.TextChoices):
    """
    Technology category for TechStackSignal.

    Classifies the type of tool or platform the account is using.
    Used for filtering and LLM prompt grouping.

    CRM           — customer relationship management
    ERP           — enterprise resource planning
    BI            — business intelligence / analytics
    HR            — human resources / HCM
    MARKETING     — marketing automation, email, ads
    SECURITY      — cybersecurity, IAM, compliance tools
    CLOUD         — cloud infrastructure, IaaS, PaaS
    COLLABORATION — communication, project management, productivity
    FINANCE       — accounting, FP&A, expense management
    OTHER         — tools that do not fit the above categories
    """
    CRM           = 'CRM',           _('CRM')
    ERP           = 'ERP',           _('ERP')
    BI            = 'BI',            _('BI & Analytics')
    HR            = 'HR',            _('HR & People')
    MARKETING     = 'MARKETING',     _('Marketing')
    SECURITY      = 'SECURITY',      _('Security')
    CLOUD         = 'CLOUD',         _('Cloud Infrastructure')
    COLLABORATION = 'COLLABORATION', _('Collaboration')
    FINANCE       = 'FINANCE',       _('Finance')
    OTHER         = 'OTHER',         _('Other')


class Satisfaction(models.TextChoices):
    """
    Rep-assessed satisfaction level of the account with a tool in TechStackSignal.

    Based on what was expressed during the conversation — not a formal score.
    UNKNOWN is the safe default when satisfaction was not discussed.

    HIGH    — account is satisfied or positive about the tool
    MEDIUM  — mixed feelings, some concerns raised
    LOW     — clear dissatisfaction or frustration expressed
    UNKNOWN — satisfaction was not discussed or is unclear
    """
    HIGH    = 'HIGH',    _('High')
    MEDIUM  = 'MEDIUM',  _('Medium')
    LOW     = 'LOW',     _('Low')
    UNKNOWN = 'UNKNOWN', _('Unknown')