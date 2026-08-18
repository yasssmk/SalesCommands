# backend/app_modules/accounts/services/filter_service.py
"""
Service for applying advanced filters to CompanyAccount querysets.

Supports:
- Direct field filters (type, classification, account_owner, etc.)
- FK filters via Subquery/Exists (tech_stack, buying_process, signals)
- Territory filter_definition application
"""

from django.db.models import Q, Exists, OuterRef
from django.utils import timezone
from datetime import timedelta
import logging

from app_modules.signals.constants import SignalStatus

logger = logging.getLogger(__name__)


class AccountFilterService:
    """
    Applies filters to CompanyAccount queryset.
    
    Usage:
        # Direct filters
        queryset = AccountFilterService.apply_filters(queryset, {
            'type': 'CLIENT',
            'classification': 'ENTERPRISE'
        })
        
        # From territory
        queryset = AccountFilterService.apply_territory_filters(
            queryset, territory_id, client_id
        )
    """
    
    # ==========================================================================
    # MAIN ENTRY POINTS
    # ==========================================================================
    
    @classmethod
    def apply_filters(cls, queryset, filter_definition, client_id=None, user=None):
        """
        Apply all filters from filter_definition dict.
        
        Args:
            queryset: CompanyAccount QuerySet
            filter_definition: dict with filter keys/values
            client_id: UUID for client scoping (optional)
            user: User instance for account_scope filtering (optional)
            
        Returns:
            Filtered QuerySet
        """
        if not filter_definition:
            return queryset
        
        # Direct field filters (including account_scope)
        queryset = cls._apply_direct_filters(queryset, filter_definition, user, client_id)
        
        # FK filters (tech_stack, buying_process, signals)
        queryset = cls._apply_fk_filters(queryset, filter_definition, client_id)
        
        return queryset
    
    @classmethod
    def apply_territory_filters(cls, queryset, territory_id, client_id, user=None):
        """
        Load territory and apply its filter_definition.
        
        Args:
            queryset: CompanyAccount QuerySet
            territory_id: UUID of territory
            client_id: UUID for client scoping
            user: User instance for account_scope filtering (optional)
            
        Returns:
            Filtered QuerySet
            
        Raises:
            Territory.DoesNotExist if not found
        """
        from app_modules.territories.models import Territory
        
        territory = Territory.objects.get(
            id=territory_id,
            client_id=client_id
        )
        
        return cls.apply_filters(queryset, territory.filter_definition, client_id, user)
    
    # ==========================================================================
    # DIRECT FIELD FILTERS
    # ==========================================================================
    
    @classmethod
    def _apply_direct_filters(cls, queryset, filter_definition, user=None, client_id=None):
        """
        Apply filters on direct CompanyAccount fields.
        
        Supports both single values and arrays for multi-select filtering.
        - Single value: filter(field=value)
        - Array: filter(field__in=values)
        
        Args:
            queryset: CompanyAccount QuerySet
            filter_definition: dict with filter keys/values
            user: User instance (for scope filtering)
            client_id: UUID for client scoping
            
        Returns:
            Filtered QuerySet
        """
        
        # Helper function to apply filter with single value or array support
        def apply_filter(qs, field_name, value):
            """Apply filter supporting both single value and array."""
            if value is None:
                return qs
            
            if isinstance(value, list):
                # Filter out empty strings and None values
                cleaned = [v for v in value if v is not None and v != '']
                if len(cleaned) > 0:
                    return qs.filter(**{f'{field_name}__in': cleaned})
            elif isinstance(value, str) and value:
                return qs.filter(**{field_name: value})
            
            return qs
        
        # Type filter (supports single value or array)
        queryset = apply_filter(queryset, 'type', filter_definition.get('type'))
        
        # Classification filter (supports single value or array)
        queryset = apply_filter(queryset, 'classification', filter_definition.get('classification'))
        
        # Industry filter (supports single value or array)
        queryset = apply_filter(queryset, 'industry', filter_definition.get('industry'))
        
        # Country filter (supports single value or array)
        queryset = apply_filter(queryset, 'country', filter_definition.get('country'))
        
        # Company size filter (supports single value or array)
        queryset = apply_filter(queryset, 'company_size', filter_definition.get('company_size'))
        
        # Account owner filter (supports single UUID, object with id, or array)
        # NOTE: Only apply if account_scope is not set (scope takes priority)
        account_scope = filter_definition.get('account_scope')
        if not account_scope or account_scope == 'all':
            account_owner = filter_definition.get('account_owner')
            if account_owner:
                # Handle different formats: UUID string, object with id, or array
                if isinstance(account_owner, list):
                    # Array of owners (UUIDs or objects)
                    owner_ids = []
                    for owner in account_owner:
                        if isinstance(owner, dict) and owner.get('id'):
                            owner_ids.append(owner['id'])
                        elif isinstance(owner, str) and owner:
                            owner_ids.append(owner)
                    if owner_ids:
                        queryset = queryset.filter(account_owner_id__in=owner_ids)
                elif isinstance(account_owner, dict) and account_owner.get('id'):
                    # Single object with id
                    queryset = queryset.filter(account_owner_id=account_owner['id'])
                elif isinstance(account_owner, str) and account_owner:
                    # Single UUID string
                    queryset = queryset.filter(account_owner_id=account_owner)
        
        # Has buying decision filter (boolean - no multi-select)
        if filter_definition.get('has_buying_decision') is not None:
            queryset = queryset.filter(
                has_buying_decision=filter_definition['has_buying_decision']
            )
        
        # Account scope filter (mine/team/all)
        queryset = cls._apply_account_scope_filter(
            queryset, filter_definition, user, client_id
        )
        
        return queryset

    @classmethod
    def _apply_account_scope_filter(cls, queryset, filter_definition, user=None, client_id=None):
        """
        Apply account_scope filter (mine/team/all).
        
        Priority rules:
        - If account_scope is 'mine' or 'team': applies scope filter, ignores account_owner
        - If account_scope is empty/all: account_owner filter applies (handled in _apply_direct_filters)
        
        Args:
            queryset: CompanyAccount QuerySet
            filter_definition: dict with filter keys/values
            user: User instance (required for mine/team scope)
            client_id: UUID for client scoping
            
        Returns:
            Filtered QuerySet
        """
        account_scope = filter_definition.get('account_scope')
        
        # No scope filter if empty, 'all', or no user provided
        if not account_scope or account_scope == 'all' or not user:
            return queryset
        
        user_id = str(user.id)
        
        if account_scope == 'mine':
            # Filter by current user only - OVERRIDES account_owner
            queryset = queryset.filter(account_owner_id=user_id)
            logger.debug("account_scope_mine_applied", extra={
                'user_id': user_id
            })
            
        elif account_scope == 'team':
            # Filter by all users in user's teams + sub-teams - OVERRIDES account_owner
            from permissions.owner_scope import get_all_descendant_team_ids, get_team_member_ids
            
            # Get user's direct team
            user_team_ids = set()
            if hasattr(user, 'team_id') and user.team_id:
                user_team_ids.add(str(user.team_id))
            
            if not user_team_ids:
                # User has no team, fallback to 'mine'
                logger.debug("account_scope_team_fallback_to_mine", extra={
                    'user_id': user_id,
                    'reason': 'no_team'
                })
                return queryset.filter(account_owner_id=user_id)
            
            # Get all descendant teams
            all_team_ids = get_all_descendant_team_ids(user_team_ids, client_id)
            
            # Get all members of those teams
            member_ids = get_team_member_ids(all_team_ids, client_id)
            
            # Include the current user
            member_ids.add(user_id)
            
            queryset = queryset.filter(account_owner_id__in=member_ids)
            logger.debug("account_scope_team_applied", extra={
                'user_id': user_id,
                'team_count': len(all_team_ids),
                'member_count': len(member_ids)
            })
        
        return queryset
    
    # ==========================================================================
    # FK FILTERS (Phase 2 - Future)
    # ==========================================================================
    
    @classmethod
    def _apply_fk_filters(cls, queryset, filter_definition, client_id=None):
        """Apply filters requiring JOINs to related models."""
        
        # Tech Stack filter
        if filter_definition.get('has_tech_stack'):
            queryset = cls._filter_by_tech_stack(
                queryset, 
                filter_definition['has_tech_stack'],
                client_id
            )
        
        # Buying Process Stage filter
        if filter_definition.get('buying_process_stage'):
            queryset = cls._filter_by_buying_process(
                queryset,
                filter_definition['buying_process_stage'],
                client_id
            )
        
        # Has Qualification filter
        if filter_definition.get('has_qualification') is not None:
            queryset = cls._filter_by_qualification(
                queryset,
                filter_definition['has_qualification'],
                client_id
            )
        
        # Signals freshness filter
        if filter_definition.get('signals_since_days'):
            queryset = cls._filter_by_signals_freshness(
                queryset,
                filter_definition['signals_since_days'],
                client_id
            )
        
        return queryset
    
    # ==========================================================================
    # TECH STACK FILTER
    # ==========================================================================
    
    @classmethod
    def _filter_by_tech_stack(cls, queryset, tech_names, client_id=None):
        """
        Filter accounts observed using at least one of the given tools.

        Source of truth (S10)
        ---------------------
        `app_modules.signals.TechStackSignal`, matched on
        `tech_name_normalized`.

        This previously queried the LEGACY `apps.accounts.TechStack`
        table (TD-61). That model belongs to the pre-modular monolith:
        nothing in the modular flow writes to it, and its `account_id`
        column is a bigint FK to the legacy `Account`, while the
        queryset being filtered is `CompanyAccount` with a UUID pk — so
        the subquery did not merely return nothing, it raised
        `ProgrammingError: operator does not exist: bigint = uuid` on
        every call. The filter was unreachable in practice.

        Matching
        --------
        EXACT on the normalised form, not substring. "accounts using
        Salesforce" must not also return accounts using "Salesforce
        Marketing Cloud" — those are different products, and a rep
        filtering for one does not expect the other. Incoming values go
        through `TechStackSignal._normalize_tech_name`, the same helper
        the model applies in save(), so a user typing "  Salesforce  "
        matches a signal stored as "salesforce" without either side
        knowing about the other's casing or spacing. Re-implementing the
        lower/trim/collapse rule here would let the two drift apart.

        Multiple values are OR'd (an account matches if it has ANY of
        the listed tools), preserving the legacy `__in` semantics.
        Blank entries are dropped so an empty string cannot match
        signals whose tech_name is itself empty.

        Status rule
        -----------
        PENDING and VALIDATED signals count; REJECTED ones do not.
        A tool mentioned on a call is real intelligence before a rep
        gets round to validating it, so excluding PENDING would hide
        most freshly-extracted evidence. REJECTED means a human looked
        at it and said no — honouring that is the whole point of the
        status. Listed explicitly rather than as `.exclude(REJECTED)`
        so that a future status has to opt in deliberately.

        Tenant scoping is preserved on the subquery, mirroring the
        sibling `_filter_by_buying_process` below.
        """
        if not tech_names:
            return queryset

        from app_modules.signals.models import TechStackSignal

        if isinstance(tech_names, str):
            tech_names = [tech_names]

        # Same normalisation the model applies in save() — reused, not
        # re-implemented, so the query key and the stored key cannot
        # diverge. Blank results are dropped (a blank filter value must
        # not match signals with an empty tech_name).
        normalised = [
            key for key in (
                TechStackSignal._normalize_tech_name(name)
                for name in tech_names
            )
            if key
        ]
        if not normalised:
            return queryset

        tech_signal_exists = TechStackSignal.objects.filter(
            account_id=OuterRef('pk'),
            tech_name_normalized__in=normalised,
            status__in=(SignalStatus.PENDING, SignalStatus.VALIDATED),
        )

        if client_id:
            tech_signal_exists = tech_signal_exists.filter(client_id=client_id)

        return queryset.filter(Exists(tech_signal_exists))
    
    # ==========================================================================
    # BUYING PROCESS FILTER
    # ==========================================================================
    
    @classmethod
    def _filter_by_buying_process(cls, queryset, stages, client_id=None):
        """Filter accounts by buying process stage."""
        if not stages:
            return queryset
        
        from apps.accounts.models import BuyingProcess
        
        if isinstance(stages, str):
            stages = [stages]
        
        buying_process_exists = BuyingProcess.objects.filter(
            account_id=OuterRef('pk'),
            current_stage__in=stages
        )
        
        if client_id:
            buying_process_exists = buying_process_exists.filter(client_id=client_id)
        
        return queryset.filter(Exists(buying_process_exists))
    
    # ==========================================================================
    # QUALIFICATION FILTER
    # ==========================================================================

    @classmethod
    def _filter_by_qualification(cls, queryset, has_qualification, client_id=None):
        """
        Filter accounts by qualification status — temporarily neutralised.

        Status: STUB — returns queryset unchanged.

        Why
        ---
        This filter previously relied on the legacy `apps.signals.models.
        QualificationSignal` model, which has been replaced by the new
        4-type architecture (PeopleSignal / PainSignal / ObjectiveSignal /
        TechStackSignal) under `app_modules.signals`. The legacy import
        was the last bridge from `app_modules` into `apps.signals`; it
        has been removed as part of Sprint 1 Phase E hygiene.

        The notion of "qualification" in the legacy model was a single
        category covering MEDPICC-style commercial data. The new
        architecture splits this concept across multiple signal types,
        so a 1-to-1 redirect would be sloppy. A proper rewrite is
        deferred to the Filtres sprint, when the team will revisit
        `AccountFilterService` filters as a coherent set against the
        new signals architecture.

        Behavioural note
        ----------------
        Until the Filtres sprint ships:
          - `has_qualification=true`   → returns ALL accounts (no narrowing)
          - `has_qualification=false`  → returns ALL accounts (no widening)
        The API endpoint accepting this query param continues to respond
        200 (no breakage), but the parameter has no effect. A WARNING is
        logged each time the filter is invoked so usage can be tracked
        in ops logs and prioritised.

        TODO (Filtres sprint)
        ---------------------
        Re-implement against the new signal types. Likely shape:
          PainSignal.objects.filter(
              account_id=OuterRef('pk'),
              status=SignalStatus.VALIDATED,
          ).exists()
        — possibly OR'd across the 4 types depending on product intent
        ("any validated signal" vs "specifically a Pain", etc.). To be
        confirmed at sprint kickoff.

        Args:
            queryset:         CompanyAccount queryset (returned unchanged).
            has_qualification: Boolean from the API caller (ignored).
            client_id:        Tenant ID (ignored).

        Returns:
            queryset (unchanged).
        """
        logger.warning(
            'AccountFilterService._filter_by_qualification called but is '
            'currently a no-op (Sprint 1 hygiene — Filtres sprint pending). '
            'has_qualification=%s, client_id=%s',
            has_qualification,
            client_id,
        )
        return queryset
    
    # ==========================================================================
    # SIGNALS FRESHNESS FILTER
    # ==========================================================================

    @classmethod
    def _filter_by_signals_freshness(cls, queryset, days, client_id=None):
        """
        Filter accounts with recent signals — temporarily neutralised.

        Status: STUB — returns queryset unchanged.

        Why
        ---
        This filter previously relied on the legacy
        `apps.signals.models.{QualificationSignal, TechStackSignal,
        ProfileSignal}` models. The 4-type architecture under
        `app_modules.signals` (PeopleSignal / PainSignal /
        ObjectiveSignal / TechStackSignal) makes this freshness check
        trivially redirectable, but rewriting filter logic in isolation
        is out of scope for Sprint 1. The Filtres sprint will revisit
        `AccountFilterService` as a coherent set.

        Behavioural note
        ----------------
        Until the Filtres sprint ships, calling this filter has no
        effect. The API endpoint accepting `signals_since_days`
        continues to respond 200 but the parameter is ignored. A
        WARNING is logged for traceability.

        TODO (Filtres sprint)
        ---------------------
        Trivial redirect — this filter has no semantic ambiguity, only
        a temporality. The new shape:

            from app_modules.signals.models import (
                PainSignal, ObjectiveSignal, TechStackSignal, PeopleSignal,
            )

            cutoff = timezone.now() - timedelta(days=int(days))
            pain_recent      = PainSignal.objects.filter(
                account_id=OuterRef('pk'), created_at__gte=cutoff,
            )
            objective_recent = ObjectiveSignal.objects.filter(
                account_id=OuterRef('pk'), created_at__gte=cutoff,
            )
            tech_recent      = TechStackSignal.objects.filter(
                account_id=OuterRef('pk'), created_at__gte=cutoff,
            )
            people_recent    = PeopleSignal.objects.filter(
                account_id=OuterRef('pk'), created_at__gte=cutoff,
            )
            # client_id scoping on each
            return queryset.filter(
                Exists(pain_recent) | Exists(objective_recent)
                | Exists(tech_recent) | Exists(people_recent),
            )

        PeopleSignal will be removed in Sprint 2 — drop the People
        branch here when the model is gone (canonical removal trace
        for that day).

        Args:
            queryset:  CompanyAccount queryset (returned unchanged).
            days:      Number of days for the freshness window (ignored).
            client_id: Tenant ID (ignored).

        Returns:
            queryset (unchanged).
        """
        logger.warning(
            'AccountFilterService._filter_by_signals_freshness called but '
            'is currently a no-op (Sprint 1 hygiene — Filtres sprint '
            'pending). days=%s, client_id=%s',
            days,
            client_id,
        )
        return queryset
    
    # ==========================================================================
    # UTILITY
    # ==========================================================================
    
    @classmethod
    def get_filter_summary(cls, filter_definition):
        """Generate human-readable summary of active filters."""
        if not filter_definition:
            return []
        
        summary = []
        
        if filter_definition.get('type'):
            summary.append(f"Type: {filter_definition['type']}")
        if filter_definition.get('classification'):
            summary.append(f"Classification: {filter_definition['classification']}")
        if filter_definition.get('account_owner'):
            summary.append("Owner: Filtered")
        if filter_definition.get('industry'):
            summary.append(f"Industry: {filter_definition['industry']}")
        if filter_definition.get('country'):
            summary.append(f"Country: {filter_definition['country']}")
        if filter_definition.get('has_tech_stack'):
            # The values are tool names as the user typed them; the
            # filter normalises them before matching (see
            # _filter_by_tech_stack), but the summary echoes the raw
            # input so it reads back exactly as it was entered.
            techs = filter_definition['has_tech_stack']
            summary.append(f"Tech Stack: {', '.join(techs) if isinstance(techs, list) else techs}")
        if filter_definition.get('buying_process_stage'):
            stages = filter_definition['buying_process_stage']
            summary.append(f"Buying Stage: {', '.join(stages) if isinstance(stages, list) else stages}")
        if filter_definition.get('has_qualification'):
            summary.append("Has Qualification")
        if filter_definition.get('signals_since_days'):
            summary.append(f"Signals: Last {filter_definition['signals_since_days']} days")
        
        return summary