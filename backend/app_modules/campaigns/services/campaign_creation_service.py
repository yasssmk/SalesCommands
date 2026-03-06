# app_modules/campaigns/services/campaign_creation_service.py
"""
CampaignCreationService — atomic campaign creation with nested entities.

Responsibilities:
    - Create Campaign instance
    - Create primary CampaignObjective (if provided)
    - Create CampaignMember entries (owner, executors, receivers)
    - Sync accounts from Territory for OUTBOUND campaigns
    - Manual account enrollment for TARGETED campaigns

All operations are atomic (caller wraps in transaction.atomic).
"""

from django.db import transaction

from core.logging import get_logger
from core.logging.audit import audit_log
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages

from app_modules.accounts.models import CompanyAccount
from app_modules.territories.models import Territory
from end_users.models import User

from ..models import (
    Campaign,
    CampaignType,
    CampaignStatus,
    CampaignAccount,
    CampaignAccountStatus,
    CampaignMember,
    CampaignObjective,
    ObjectiveType,
)
from ..config.settings import CONFIG

logger = get_logger(__name__)


class CampaignCreationService:
    """
    Service for creating campaigns with all related entities.

    Usage:
        service = CampaignCreationService(user=request.user, client_id=client_id)
        result = service.create_campaign(data)
    """

    def __init__(self, user, client_id):
        self.user = user
        self.client_id = str(client_id)

    # ======================================================================
    # PUBLIC API
    # ======================================================================

    @transaction.atomic
    def create_campaign(self, data):
        """
        Create a campaign with optional nested objective, members, and accounts.

        Args:
            data (dict): {
                # Required
                'name': str,
                'campaign_type': str,  # OUTBOUND | TARGETED
                'start_date': date,
                'end_date': date,

                # Optional
                'description': str,
                'sequence_type': str,
                'territory_ids': [UUID],

                # Nested (optional)
                'objective': {name, objective_type, target_value, is_primary},
                'owner_ids': [UUID],
                'executor_ids': [UUID],
                'receiver_ids': [UUID],
                'account_ids': [UUID],  # TARGETED only: manual account enrollment
            }

        Returns:
            dict: {
                'campaign': Campaign instance,
                'objective': CampaignObjective or None,
                'members': [CampaignMember],
                'accounts_enrolled': int,
            }
        """
        logger.info("campaign_creation_started", extra={
            'client_id': self.client_id,
            'campaign_name': data.get('name'),
            'campaign_type': data.get('campaign_type'),
        })

        # 1. Create campaign
        campaign = self._create_campaign(data)

        # 2. Create objective (if provided)
        objective = self._create_objective(campaign, data.get('objective'))

        # 3. Create members
        members = self._create_members(campaign, data)

        # 4. Enroll accounts
        accounts_enrolled = self._enroll_accounts(campaign, data)

        # Audit
        audit_log(
            event='campaign_created',
            action='create',
            actor_id=str(self.user.id),
            client_id=self.client_id,
            target_type='campaign',
            target_id=str(campaign.id),
            outcome='success',
            extra={
                'campaign_name': campaign.name,
                'campaign_type': campaign.campaign_type,
                'has_objective': objective is not None,
                'members_count': len(members),
                'accounts_enrolled': accounts_enrolled,
            }
        )

        logger.info("campaign_creation_success", extra={
            'client_id': self.client_id,
            'campaign_id': str(campaign.id),
            'accounts_enrolled': accounts_enrolled,
        })

        return {
            'campaign': campaign,
            'objective': objective,
            'members': members,
            'accounts_enrolled': accounts_enrolled,
        }

    # ======================================================================
    # PRIVATE — CAMPAIGN
    # ======================================================================

    def _create_campaign(self, data):
        """Create the Campaign instance."""
        # Resolve territories (M2M)
        territory_ids = data.get('territory_ids', [])
        territories = []
        for tid in territory_ids:
            try:
                territory = Territory.objects.get(id=tid, client_id=self.client_id)
                territories.append(territory)
            except Territory.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        # OUTBOUND requires at least one territory
        campaign_type = data.get('campaign_type')
        if campaign_type == CampaignType.OUTBOUND and not territories:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_TERRITORY_REQUIRED
            )

        campaign = Campaign(
            name=data['name'],
            description=data.get('description', ''),
            campaign_type=campaign_type,
            sequence_type=data.get('sequence_type'),
            start_date=data['start_date'],
            end_date=data['end_date'],
            status=CampaignStatus.DRAFT,
        )
        campaign.save(user=self.user, client_id=self.client_id)

        # Set M2M territories
        if territories:
            campaign.territories.set(territories)

        return campaign


    # ======================================================================
    # PRIVATE — OBJECTIVE
    # ======================================================================

    def _create_objective(self, campaign, objective_data):
        """Create CampaignObjective if data provided."""
        if not objective_data:
            return None

        objective = CampaignObjective(
            campaign=campaign,
            name=objective_data['name'],
            objective_type=objective_data['objective_type'],
            target_value=objective_data['target_value'],
            is_primary=objective_data.get('is_primary', True),
        )
        objective.save(user=self.user, client_id=self.client_id)

        logger.info("campaign_objective_created", extra={
            'campaign_id': str(campaign.id),
            'objective_type': objective.objective_type,
        })

        return objective

    # ======================================================================
    # PRIVATE — MEMBERS
    # ======================================================================

    def _create_members(self, campaign, data):
        """
        Create CampaignMember entries from owner_ids, executor_ids, receiver_ids.

        If no owner_ids provided, the current user becomes primary owner.
        """
        members = []

        owner_ids = data.get('owner_ids', [])
        executor_ids = data.get('executor_ids', [])
        receiver_ids = data.get('receiver_ids', [])

        # Owners
        for i, uid in enumerate(owner_ids):
            member = self._add_member(campaign, uid, CampaignMember.MemberRole.OWNER, is_primary=(i == 0))
            if member:
                members.append(member)

        # Executors
        for uid in executor_ids:
            member = self._add_member(campaign, uid, CampaignMember.MemberRole.EXECUTOR)
            if member:
                members.append(member)

        # Receivers
        for uid in receiver_ids:
            member = self._add_member(campaign, uid, CampaignMember.MemberRole.RECEIVER)
            if member:
                members.append(member)

        # Default: current user as primary owner if no owner provided
        if not owner_ids:
            member = campaign.add_member(
                user=self.user,
                role=CampaignMember.MemberRole.OWNER,
                added_by=self.user,
                is_primary_owner=True,
            )
            members.append(member)

        return members

    def _add_member(self, campaign, user_id, role, is_primary=False):
        """Add a single member after validating user belongs to client."""
        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            logger.warning("campaign_member_user_not_found", extra={
                'campaign_id': str(campaign.id),
                'user_id': str(user_id),
            })
            return None

        if str(user.client_account_id) != self.client_id:
            logger.warning("campaign_member_client_mismatch", extra={
                'campaign_id': str(campaign.id),
                'user_id': str(user_id),
            })
            return None

        return campaign.add_member(
            user=user,
            role=role,
            added_by=self.user,
            is_primary_owner=is_primary,
        )

    # ======================================================================
    # PRIVATE — ACCOUNT ENROLLMENT
    # ======================================================================

    def _enroll_accounts(self, campaign, data):
        """
        Enroll accounts into campaign.

        - OUTBOUND: pull accounts from all campaign territories
        - TARGETED: enroll from explicit account_ids list
        """
        if campaign.campaign_type == CampaignType.OUTBOUND:
            return self._enroll_from_territories(campaign)
        else:
            # TARGETED: manual account_ids
            account_ids = data.get('account_ids', [])
            return self._enroll_from_ids(campaign, account_ids)


    def _enroll_from_territories(self, campaign):
        """
        Pull accounts from all campaign territories and enroll them.

        Applies filter logic from each territory, unions the results,
        then enrolls up to max_accounts_per_campaign.
        """
        territories = campaign.territories.all()
        if not territories:
            return 0

        # Union accounts from all territories
        combined_qs = CompanyAccount.objects.none()
        for territory in territories:
            qs = CompanyAccount.objects.filter(client_id=campaign.client_id)
            if territory.filter_definition:
                qs = self._apply_territory_filters(qs, territory.filter_definition)
            combined_qs = combined_qs | qs

        combined_qs = combined_qs.distinct()
        total_matching = combined_qs.count()

        # Respect max accounts limit
        max_accounts = CONFIG.limits.max_accounts_per_campaign
        accounts = list(combined_qs[:max_accounts])

        logger.info("campaign_territory_enrollment_debug", extra={
            'campaign_id': str(campaign.id),
            'territory_count': territories.count(),
            'client_id': str(campaign.client_id),
            'total_matching_accounts': total_matching,
            'accounts_to_enroll': len(accounts),
            'max_accounts_limit': max_accounts,
        })

        enrolled = 0
        for account in accounts:
            if CampaignAccount.objects.filter(campaign=campaign, account=account).exists():
                continue

            CampaignAccount(
                campaign=campaign,
                account=account,
                status=CampaignAccountStatus.PENDING,
            ).save(user=self.user, client_id=self.client_id)
            enrolled += 1

        logger.info("campaign_accounts_enrolled_from_territories", extra={
            'campaign_id': str(campaign.id),
            'territory_count': territories.count(),
            'accounts_enrolled': enrolled,
            'accounts_skipped_duplicate': len(accounts) - enrolled,
        })

        return enrolled



    def _enroll_from_ids(self, campaign, account_ids):
        """Enroll accounts from explicit ID list (TARGETED campaigns)."""
        if not account_ids:
            return 0

        accounts = CompanyAccount.objects.filter(
            id__in=account_ids,
            client_id=self.client_id,
        )

        enrolled = 0
        for account in accounts:
            # Skip duplicates
            if CampaignAccount.objects.filter(campaign=campaign, account=account).exists():
                continue

            CampaignAccount(
                campaign=campaign,
                account=account,
                status=CampaignAccountStatus.PENDING,
            ).save(user=self.user, client_id=self.client_id)
            enrolled += 1

        logger.info("campaign_accounts_enrolled_from_ids", extra={
            'campaign_id': str(campaign.id),
            'accounts_enrolled': enrolled,
            'requested': len(account_ids),
        })

        return enrolled

    # ======================================================================
    # PRIVATE — TERRITORY FILTER APPLICATION
    # ======================================================================

    def _apply_territory_filters(self, queryset, filters):
        """
        Apply territory filter_definition to CompanyAccount queryset.

        Mirrors TerritoryViewSet._count_accounts_for_territory() logic.
        """
        # Type filter
        if filters.get('type'):
            type_val = filters['type']
            if isinstance(type_val, list):
                queryset = queryset.filter(type__in=type_val)
            else:
                queryset = queryset.filter(type=type_val)

        # Classification filter
        if filters.get('classification'):
            class_val = filters['classification']
            if isinstance(class_val, list):
                queryset = queryset.filter(classification__in=class_val)
            else:
                queryset = queryset.filter(classification=class_val)

        # Industry filter
        if filters.get('industry'):
            industry_val = filters['industry']
            if isinstance(industry_val, list):
                queryset = queryset.filter(industry__in=industry_val)
            else:
                queryset = queryset.filter(industry=industry_val)

        # Country filter
        if filters.get('country'):
            country_val = filters['country']
            if isinstance(country_val, list):
                queryset = queryset.filter(country__in=country_val)
            else:
                queryset = queryset.filter(country=country_val)

        # Account owner filter
        if filters.get('account_owner'):
            queryset = queryset.filter(account_owner_id=filters['account_owner'])

        # Account scope filter (mine/team)
        if filters.get('account_scope'):
            scope = filters['account_scope']
            if scope == 'mine':
                queryset = queryset.filter(account_owner=self.user)
            elif scope == 'team':
                if self.user.team_id:
                    queryset = queryset.filter(account_owner__team_id=self.user.team_id)

        return queryset