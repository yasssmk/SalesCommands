# backend/app_modules/contacts/services/filter_service.py
"""
Service for applying territory filters to Contact querysets.

Mirrors AccountFilterService (accounts/services/filter_service.py): the single
place that turns a territory ``filter_definition`` into a filtered Contact
queryset, so every consumer (workspace stats, the batched counts endpoint)
evaluates contact membership the same way and can never drift apart.

Supported keys (subset of ALLOWED_FILTER_KEYS relevant to contacts):
    - influence_level      (scalar or list)
    - standard_department  (scalar or list, FK id)
    - has_buying_authority (boolean)
    - opted_out            (boolean)
    - contact_scope        ('mine' | 'team' | 'all')
"""

import logging

logger = logging.getLogger(__name__)


class ContactFilterService:
    """
    Applies filters to a Contact queryset.

    Usage:
        queryset = ContactFilterService.apply_filters(
            Contact.objects.filter(client_id=client_id),
            territory.filter_definition,
            user=territory.owner,
        )
    """

    # ==========================================================================
    # MAIN ENTRY POINT
    # ==========================================================================

    @classmethod
    def apply_filters(cls, queryset, filter_definition, user=None):
        """
        Apply all contact filters from a filter_definition dict.

        Args:
            queryset: Contact QuerySet (caller is responsible for client scoping)
            filter_definition: dict with filter keys/values
            user: User instance for contact_scope (mine/team) filtering

        Returns:
            Filtered QuerySet (lazy — no count/exists evaluated here)
        """
        if not filter_definition:
            return queryset

        queryset = cls._apply_direct_filters(queryset, filter_definition)
        queryset = cls._apply_contact_scope_filter(queryset, filter_definition, user)
        return queryset

    # ==========================================================================
    # DIRECT FIELD FILTERS
    # ==========================================================================

    @classmethod
    def _apply_direct_filters(cls, queryset, filter_definition):
        """
        Apply filters on direct Contact fields.

        Scalar and array values are both supported for the choice/FK fields:
        - Single value: filter(field=value)
        - Array:        filter(field__in=values)

        Boolean fields (has_buying_authority, opted_out) are applied whenever
        the key is present with a non-None value, so an explicit ``false`` is
        honoured (not treated as "unset").
        """

        def apply_choice_filter(qs, field_name, value):
            """Apply a choice/FK filter supporting a single value or an array."""
            if value is None:
                return qs
            if isinstance(value, list):
                cleaned = [v for v in value if v is not None and v != '']
                if cleaned:
                    return qs.filter(**{f'{field_name}__in': cleaned})
                return qs
            if isinstance(value, str) and value:
                return qs.filter(**{field_name: value})
            return qs

        # Influence level (scalar or array)
        queryset = apply_choice_filter(
            queryset, 'influence_level', filter_definition.get('influence_level')
        )

        # Standard department (scalar or array, FK id)
        queryset = apply_choice_filter(
            queryset, 'standard_department_id', filter_definition.get('standard_department')
        )

        # Has buying authority (boolean — explicit false honoured)
        if filter_definition.get('has_buying_authority') is not None:
            queryset = queryset.filter(
                has_buying_authority=filter_definition['has_buying_authority']
            )

        # Opted out (boolean — explicit false honoured)
        if filter_definition.get('opted_out') is not None:
            queryset = queryset.filter(
                opted_out=filter_definition['opted_out']
            )

        return queryset

    # ==========================================================================
    # CONTACT SCOPE FILTER (mine / team)
    # ==========================================================================

    @classmethod
    def _apply_contact_scope_filter(cls, queryset, filter_definition, user=None):
        """
        Apply the contact_scope filter via the owning account's owner.

        - 'mine': contacts whose account is owned by the current user.
        - 'team': contacts whose account owner is in the user's direct team.
          This is a FLAT team match (account__account_owner__team_id), kept
          intentionally shallower than AccountFilterService's descendant-team
          scope to preserve the historical contact-count behaviour. When the
          user has no team the scope is left unapplied — matching the original
          behaviour exactly (no mine-fallback), so counts do not shift.
        - empty / 'all' / no user: no scope narrowing.
        """
        scope = filter_definition.get('contact_scope')
        if not scope or scope == 'all' or not user:
            return queryset

        if scope == 'mine':
            return queryset.filter(account__account_owner=user)

        if scope == 'team' and getattr(user, 'team_id', None):
            return queryset.filter(account__account_owner__team_id=user.team_id)

        return queryset
