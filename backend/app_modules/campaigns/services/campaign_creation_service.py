# app_modules/campaigns/services/campaign_creation_service.py
"""
CampaignCreationService — atomic campaign creation with nested entities.

Responsibilities:
    - Create Campaign instance (owner + optional executor)
    - Create primary CampaignObjective (if provided)
    - Sync accounts from Territory for OUTBOUND campaigns
    - Manual account enrollment for TARGETED campaigns
"""

from django.db import transaction
from django.utils import timezone

from core.logging import get_logger
from core.logging.audit import audit_log
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages

from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact
from app_modules.territories.models import Territory
from end_users.models import User

from ..models import (
    Campaign,
    CampaignType,
    CampaignStatus,
    CampaignAccount,
    CampaignAccountStatus,
    CampaignObjective,
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
        Create a campaign with optional nested objective and accounts.

        Args:
            data (dict): {
                'name': str,
                'campaign_type': str,  # OUTBOUND | TARGETED
                'start_date': date,
                'end_date': date,
                'description': str (optional),
                'sequence_type': str (optional),
                'territory_ids': [UUID] (optional),
                'executor_id': UUID (optional),
                'objective': {objective_type, target_value, name?} (optional),
                'account_ids': [UUID] (optional, TARGETED only),
            }

        Returns:
            dict: {
                'campaign': Campaign instance,
                'objective': CampaignObjective or None,
                'accounts_enrolled': int,
            }
        """
        logger.info("campaign_creation_started", extra={
            'client_id': self.client_id,
            'campaign_name': data.get('name'),
            'campaign_type': data.get('campaign_type'),
        })

        campaign = self._create_campaign(data)
        objective = self._create_objective(campaign, data.get('objective'))
        accounts_enrolled = self._enroll_accounts(campaign, data)

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
                'accounts_enrolled': accounts_enrolled,
                'executor_id': str(campaign.executor_id) if campaign.executor_id else None,
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
            'accounts_enrolled': accounts_enrolled,
        }

    # ======================================================================
    # PUBLIC API — TARGETED SINGLETON
    # ======================================================================

    @transaction.atomic
    def get_or_create_targeted(self, sequence_type, name=None):
        """
        Get or create the TARGETED singleton campaign for this user.

        One TARGETED campaign per (client_id, owner, campaign_type=TARGETED).
        Created directly in ACTIVE status — no lifecycle transition needed.

        Args:
            sequence_type (str): e.g. 'TARGETED'
            name (str): optional name override

        Returns:
            tuple: (Campaign, created: bool)
        """
        from django.db import IntegrityError

        today = timezone.now().date()
        far_future = today.replace(year=today.year + 10)

        try:
            campaign, created = Campaign.objects.get_or_create(
                client_id=self.client_id,
                campaign_type=CampaignType.TARGETED,
                owner=self.user,
                defaults={
                    'name': name or "My Targeted Campaign",
                    'sequence_type': sequence_type,
                    'planned_start_date': today,
                    'planned_end_date': far_future,
                    'actual_start_date': today,
                    'status': CampaignStatus.ACTIVE,
                },
            )
        except IntegrityError:
            # Concurrent request created the campaign between our check and insert.
            # The UniqueConstraint unique_targeted_campaign_per_user guarantees
            # exactly one exists — fetch it.
            campaign = Campaign.objects.get(
                client_id=self.client_id,
                campaign_type=CampaignType.TARGETED,
                owner=self.user,
            )
            return campaign, False

        if not created:
            return campaign, False

        campaign.save(user=self.user, client_id=self.client_id)
        
        audit_log(
            event='targeted_campaign_created',
            action='create',
            actor_id=str(self.user.id),
            client_id=self.client_id,
            target_type='campaign',
            target_id=str(campaign.id),
            outcome='success',
            extra={'sequence_type': sequence_type},
        )

        logger.info("targeted_campaign_created", extra={
            'client_id': self.client_id,
            'campaign_id': str(campaign.id),
            'user_id': str(self.user.id),
            'sequence_type': sequence_type,
        })

        return campaign, True

    # ======================================================================
    # PRIVATE — CAMPAIGN
    # ======================================================================

    def _create_campaign(self, data):
        """Create the Campaign instance with owner and optional executor."""
        territory_ids = data.get('territory_ids', [])
        territories = []
        for tid in territory_ids:
            try:
                territory = Territory.objects.get(id=tid, client_id=self.client_id)
                territories.append(territory)
            except Territory.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        campaign_type = data.get('campaign_type')
        if campaign_type == CampaignType.OUTBOUND and not territories:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_TERRITORY_REQUIRED
            )

        # Resolve optional executor
        executor = None
        executor_id = data.get('executor_id')
        if executor_id:
            try:
                executor = User.objects.get(id=executor_id, is_active=True)
                if str(executor.client_account_id) != self.client_id:
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            except User.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        campaign = Campaign(
            name=data['name'],
            description=data.get('description', ''),
            campaign_type=campaign_type,
            sequence_type=data.get('sequence_type'),
            planned_start_date=data['start_date'],
            planned_end_date=data['end_date'],
            status=CampaignStatus.DRAFT,
            owner=self.user,
            executor=executor,
        )
        campaign.save(user=self.user, client_id=self.client_id)

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
            name=objective_data.get('name') or f"{objective_data['objective_type'].replace('_', ' ').title()} Goal",
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
    # PRIVATE — ACCOUNT ENROLLMENT
    # ======================================================================

    def _enroll_accounts(self, campaign, data):
        """Enroll accounts — from territories (OUTBOUND) or explicit IDs (TARGETED)."""
        if campaign.campaign_type == CampaignType.OUTBOUND:
            return self._enroll_from_territories(campaign)
        account_ids = data.get('account_ids', [])
        return self._enroll_from_ids(campaign, account_ids)

    # APRÈS
    def _enroll_from_territories(self, campaign):
        """
        Pull accounts from all campaign territories and enroll them.

        Also pre-creates CampaignContact rows in PENDING so TargetsTab
        shows contacts before Start is clicked. Activities are generated at start().
        """
        from django.db.models import Q
        from ..models import CampaignContact, CampaignContactStatus

        territories = campaign.territories.all()
        if not territories:
            return 0

        combined_qs = CompanyAccount.objects.none()
        for territory in territories:
            qs = CompanyAccount.objects.filter(client_id=campaign.client_id)
            if territory.filter_definition:
                qs = self._apply_territory_filters(qs, territory.filter_definition)
            combined_qs = combined_qs | qs

        combined_qs = combined_qs.distinct()
        max_accounts = CONFIG.limits.max_accounts_per_campaign
        accounts = list(combined_qs[:max_accounts])

        enrolled = 0
        for account in accounts:
            ca, created = CampaignAccount.objects.get_or_create(
                campaign=campaign,
                account=account,
                client_id=self.client_id,
                defaults={
                    'status': CampaignAccountStatus.PENDING,
                },
            )
            if created:
                ca.save(user=self.user, client_id=self.client_id)
                enrolled += 1

            # Pre-create CampaignContacts in PENDING (reachable contacts only)
            contacts = Contact.objects.filter(
                account=account,
                client_id=self.client_id,
                opted_out=False,
            ).filter(
                Q(email__isnull=False) | Q(phone_number__isnull=False)
            ).exclude(
                Q(email='') & Q(phone_number='')
            )

            for contact in contacts:
                CampaignContact.objects.get_or_create(
                    campaign_account=ca,
                    contact=contact,
                    defaults={
                        'client_id': self.client_id,
                        'status': CampaignContactStatus.PENDING,
                    },
                )

        logger.info("campaign_accounts_enrolled_from_territories", extra={
            'campaign_id': str(campaign.id),
            'accounts_enrolled': enrolled,
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

        # Pre-fetch existing enrollments in a single query to avoid N+1
        existing_account_ids = set(
            CampaignAccount.objects.filter(
                campaign=campaign,
                account_id__in=account_ids,
            ).values_list('account_id', flat=True)
        )

        enrolled = 0
        for account in accounts:
            if account.id in existing_account_ids:
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
        })

        return enrolled

    def _apply_territory_filters(self, queryset, filters):
        """Apply territory filter_definition to CompanyAccount queryset."""
        from app_modules.accounts.services.filter_service import AccountFilterService
        return AccountFilterService.apply_filters(
            queryset, filters, str(self.client_id), self.user
        )