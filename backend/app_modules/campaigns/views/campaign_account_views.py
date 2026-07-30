# app_modules/campaigns/views/campaign_account_views.py
"""
CampaignAccountViewSet — CRUD + bulk enrollment + status actions.

Follows ActivityViewSet / TerritoryViewSet patterns:
    - BaseAPIView + ScopedQuerysetMixin
    - Response({'success': True, 'data': ...})
    - Redis caching with tag invalidation
    - Structured logging + SOC 2 audit trail
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Count, Q

from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.cache_utils import invalidate_tag

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact
from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityStatus

from ..models import (
    Campaign,
    CampaignAccount,
    CampaignAccountStatus,
    CampaignStatus,
)
from ..constants import FINAL_ACCOUNT_STATES, MAX_ACCOUNTS_PER_CAMPAIGN
from ..serializers import (
    CampaignAccountListSerializer,
    CampaignAccountDetailSerializer,
    CampaignAccountSerializer,
)
from ..services.campaign_execution_service import CampaignExecutionService
from ..config.settings import CONFIG

logger = get_logger(__name__)


class CampaignAccountViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing CampaignAccount enrollments.

    Endpoints:
        GET    /campaign-accounts/                          - List
        POST   /campaign-accounts/                          - Enroll account
        GET    /campaign-accounts/{id}/                     - Retrieve
        PATCH  /campaign-accounts/{id}/                     - Update (notes, targets)
        DELETE /campaign-accounts/{id}/                     - Remove enrollment

        POST   /campaign-accounts/{id}/start-progress/      - PENDING → IN_PROGRESS
        POST   /campaign-accounts/{id}/mark-completed/      - → COMPLETED
        POST   /campaign-accounts/{id}/mark-stopped/        - → STOPPED

        POST   /campaign-accounts/bulk-add/                 - Bulk enroll accounts
        POST   /campaign-accounts/bulk-remove/              - Bulk remove accounts

        GET    /campaign-accounts/by-campaign/              - Filter by campaign_id
    """

    queryset = CampaignAccount.objects.all()
    serializer_class = CampaignAccountSerializer
    entity_name = 'campaign_account'

    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'campaign': ['exact'],
        'account': ['exact'],
        'status': ['exact', 'in'],
    }
    search_fields = CONFIG.filters.campaign_account_search
    ordering_fields = ['status','created_at']
    ordering = CONFIG.filters.default_campaign_account_ordering

    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'campaigns'

    # Action policies
    action_policies = {
        'start_progress': {'crud': 'update', 'scope': 'mine'},
        'mark_completed': {'crud': 'update', 'scope': 'mine'},
        'mark_stopped': {'crud': 'update', 'scope': 'mine'},
        'bulk_add': {'crud': 'create', 'scope': 'mine'},
        'bulk_remove': {'crud': 'delete', 'scope': 'mine'},
        'by_campaign': {'crud': 'read', 'scope': 'client'},
        'toggle_contact': {'crud': 'update', 'scope': 'mine'},
        'enroll_target':  {'crud': 'create', 'scope': 'mine'},
    }

    # ==========================================================================
    # CACHE HELPERS
    # ==========================================================================

    def _invalidate_caches(self, client_id):
        """Invalidate campaign-related caches."""
        client_id_str = str(client_id)
        invalidate_tag(client_id_str, 'campaigns')
        invalidate_tag(client_id_str, 'activities')

    # ==========================================================================
    # SERIALIZER SELECTION
    # ==========================================================================

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return CampaignAccountListSerializer
        elif self.action == 'retrieve':
            return CampaignAccountDetailSerializer
        return CampaignAccountSerializer

    # ==========================================================================
    # QUERYSET
    # ==========================================================================

    def get_queryset(self):
        """Get filtered queryset with optimized prefetching."""
        queryset = super().get_queryset()

        if self.action == 'list':
            queryset = queryset.select_related(
                'campaign', 'account',
            ).annotate(
                _contacts_count=Count('target_contacts', distinct=True),
            )
        elif self.action == 'retrieve':
            queryset = queryset.select_related(
                'campaign', 'account',
                'created_by', 'updated_by',
            ).prefetch_related(
                'target_departments',
                'target_contacts',
                'target_contacts__standard_department',
            )
        else:
            queryset = queryset.select_related('campaign', 'account')

        return queryset

    # ==========================================================================
    # LIST
    # ==========================================================================

    def list(self, request, *args, **kwargs):
        """
        List campaign accounts with pagination.
        GET /campaign-accounts/
        """
        ctx = ctx_from_request(request)
        logger.info("campaign_accounts_list_requested", extra=ctx)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                },
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            },
        })

    # ==========================================================================
    # RETRIEVE
    # ==========================================================================

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single campaign account.
        GET /campaign-accounts/{id}/
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("campaign_account_retrieved", extra={
            **ctx, 'campaign_account_id': str(instance.id),
        })

        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})

    # ==========================================================================
    # CREATE
    # ==========================================================================

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Enroll an account into a campaign.
        POST /campaign-accounts/
        """
        ctx = ctx_from_request(request)
        logger.info("campaign_account_create_requested", extra=ctx)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='campaign_account_enrolled',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_account',
            target_id=str(instance.id),
            outcome='success',
        )

        self._invalidate_caches(self.get_client_id())

        output = CampaignAccountDetailSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': output.data,
        }, status=status.HTTP_201_CREATED)

    # ==========================================================================
    # UPDATE
    # ==========================================================================

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """
        Update campaign account (notes, target_departments, target_contacts).
        PATCH /campaign-accounts/{id}/
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("campaign_account_update_requested", extra={
            **ctx, 'campaign_account_id': str(instance.id),
        })

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='campaign_account_updated',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_account',
            target_id=str(instance.id),
            outcome='success',
        )

        self._invalidate_caches(self.get_client_id())

        output = CampaignAccountDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': output.data})

    # ==========================================================================
    # DELETE
    # ==========================================================================

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Remove account from campaign.
        DELETE /campaign-accounts/{id}/

        Only PENDING accounts can be removed.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        if instance.status != CampaignAccountStatus.PENDING:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.ACCOUNT_INVALID_STATE.format(
                    state=instance.get_status_display()
                )
            )

        ca_id = str(instance.id)

        logger.info("campaign_account_delete_requested", extra={
            **ctx, 'campaign_account_id': ca_id,
        })

        instance.delete()

        audit_log(
            event='campaign_account_removed',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_account',
            target_id=ca_id,
            outcome='success',
        )

        self._invalidate_caches(self.get_client_id())

        return Response({
            'success': True,
            'data': None,
        }, status=status.HTTP_204_NO_CONTENT)

    # ==========================================================================
    # STATUS ACTIONS
    # ==========================================================================

    @action(detail=True, methods=['post'], url_path='start-progress')
    @transaction.atomic
    def start_progress(self, request, pk=None):
        """
        PENDING → IN_PROGRESS.
        POST /campaign-accounts/{id}/start-progress/
        """
        instance = self.get_object()
        result = instance.start_progress(user=request.user, notes=request.data.get('notes'))

        self._audit_status_change(request, instance, result)
        self._invalidate_caches(self.get_client_id())

        output = CampaignAccountDetailSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'campaign_account': output.data,
                'transition': result,
            },
        })

    @action(detail=True, methods=['post'], url_path='mark-completed')
    @transaction.atomic
    def mark_completed(self, request, pk=None):
        """
        IN_PROGRESS/CALLBACK_PENDING → COMPLETED.
        POST /campaign-accounts/{id}/mark-completed/
        """
        instance = self.get_object()
        result = instance.mark_completed(
            user=request.user,
            notes=request.data.get('notes'),
        )

        self._audit_status_change(request, instance, result)
        self._invalidate_caches(self.get_client_id())

        output = CampaignAccountDetailSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'campaign_account': output.data,
                'transition': result,
            },
        })

    @action(detail=True, methods=['post'], url_path='mark-stopped')
    @transaction.atomic
    def mark_stopped(self, request, pk=None):
        """
        Any non-final → STOPPED.
        POST /campaign-accounts/{id}/mark-stopped/

        Body:
            - reason: str (optional)
            - notes: str (optional)
        """
        instance = self.get_object()
        result = instance.mark_stopped(
            reason=request.data.get('reason'),
            user=request.user,
            notes=request.data.get('notes'),
        )

        self._audit_status_change(request, instance, result)
        self._invalidate_caches(self.get_client_id())

        output = CampaignAccountDetailSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'campaign_account': output.data,
                'transition': result,
            },
        })

    # ==========================================================================
    # CONTACT TARGETING
    # ==========================================================================

    @action(detail=True, methods=['post'], url_path='toggle-contact')
    @transaction.atomic
    def toggle_contact(self, request, pk=None):
        """
        Add or remove a contact from target_contacts.
        POST /campaign-accounts/{id}/toggle-contact/

        Body:
            - contact_id: UUID

        When adding a contact to an ACTIVE campaign with activities_generated=True,
        activities are automatically generated for that contact.
        When removing, PLANNED activities for that contact are deleted.
        """
        instance = self.get_object()
        contact_id = request.data.get('contact_id')

        if not contact_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='contact_id')
            )

        client_id = self.get_client_id()

        try:
            contact = Contact.objects.get(id=contact_id, client_id=client_id)
        except Contact.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        if str(contact.account_id) != str(instance.account_id):
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND
            )
            

        campaign = instance.campaign
        is_targeted = instance.target_contacts.filter(id=contact.id).exists()

        if is_targeted:
            # Remove contact
            instance.target_contacts.remove(contact)
            action_taken = 'removed'

            # Cancel PLANNED activities and delete CampaignContact.
            # Order matters: Activity.campaign_contact FK is SET_NULL —
            # deleting CampaignContact first would orphan PLANNED activities.
            exec_service = CampaignExecutionService(
                user=request.user, client_id=client_id,
            )
            exec_service.delete_activities_for_contact(campaign, instance, contact)

            # If this was the last contact, transition the account to its
            # terminal state (COMPLETED or STOPPED).
            from ..models import CampaignContact
            if not CampaignContact.objects.filter(campaign_account=instance).exists():
                exec_service._check_account_completion(instance)

        else:
            # Add contact
            instance.target_contacts.add(contact)
            action_taken = 'added'

            # Always create CampaignContact so it appears in TargetsTab
            from ..models import CampaignContact, CampaignContactStatus
            CampaignContact.objects.get_or_create(
                campaign_account=instance,
                contact=contact,
                defaults={
                    'client_id': client_id,
                    'status': (
                        CampaignContactStatus.IN_PROGRESS
                        if campaign.status == CampaignStatus.ACTIVE
                        else CampaignContactStatus.PENDING
                    ),
                },
            )

            # Generate activities if ACTIVE (TARGETED always active, OUTBOUND after start)
            if campaign.status == CampaignStatus.ACTIVE:
                service = CampaignExecutionService(
                    user=request.user, client_id=client_id,
                )
                service.generate_activities_for_contact(campaign, instance, contact)

        audit_log(
            event='campaign_account_contact_toggled',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign_account',
            target_id=str(instance.id),
            outcome='success',
            extra={
                'contact_id': str(contact.id),
                'action': action_taken,
            },
        )

        self._invalidate_caches(client_id)

        logger.info("campaign_account_contact_toggled", extra={
            'campaign_account_id': str(instance.id),
            'contact_id': str(contact.id),
            'action': action_taken,
        })

        output = CampaignAccountDetailSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'campaign_account': output.data,
                'contact_id': str(contact.id),
                'action': action_taken,
            },
        })

    # ==========================================================================
    # BULK ACTIONS
    # ==========================================================================

    @action(detail=False, methods=['post'], url_path='bulk-add')
    @transaction.atomic
    def bulk_add(self, request):
        """
        Bulk enroll accounts into a campaign.
        POST /campaign-accounts/bulk-add/

        Body:
            - campaign_id: UUID
            - account_ids: [UUID]
        """
        ctx = ctx_from_request(request)
        campaign_id = request.data.get('campaign_id')
        account_ids = request.data.get('account_ids', [])

        if not campaign_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='campaign_id')
            )
        if not account_ids:
            raise StandardizedValidationError(
                CoreErrorMessages.BULK_NO_DATA.format(entity='account_ids')
            )

        # Validate limits
        max_items = CONFIG.limits.bulk_operation_limit
        if len(account_ids) > max_items:
            raise StandardizedValidationError(
                CoreErrorMessages.BULK_SIZE_EXCEEDED.format(
                    max_size=max_items, entity='accounts'
                )
            )

        client_id = self.get_client_id()
        campaign = self._get_campaign_scoped(campaign_id)

        # Per-campaign account cap — count only ACTIVE (non-terminal) enrollments,
        # consistent with enroll-target. Terminal accounts (COMPLETED/STOPPED)
        # do not count toward the limit.
        active_count = CampaignAccount.objects.filter(
            campaign=campaign,
        ).exclude(status__in=FINAL_ACCOUNT_STATES).count()
        if active_count + len(account_ids) > MAX_ACCOUNTS_PER_CAMPAIGN:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.MAX_ACCOUNTS_EXCEEDED.format(
                    max=MAX_ACCOUNTS_PER_CAMPAIGN
                )
            )

        # Get valid accounts
        accounts = CompanyAccount.objects.filter(
            id__in=account_ids, client_id=client_id,
        )

        # Existing enrollments
        existing = set(
            CampaignAccount.objects.filter(
                campaign=campaign, account_id__in=account_ids,
            ).values_list('account_id', flat=True)
        )

        # Status depends on campaign state: active campaigns enroll directly IN_PROGRESS
        initial_status = (
            CampaignAccountStatus.IN_PROGRESS
            if campaign.status == CampaignStatus.ACTIVE
            else CampaignAccountStatus.PENDING
        )

        from ..models import CampaignContact, CampaignContactStatus

        exec_service = (
            CampaignExecutionService(user=request.user, client_id=client_id)
            if campaign.status == CampaignStatus.ACTIVE
            else None
        )

        created_accounts = []
        skipped = 0
        for account in accounts:
            if account.id in existing:
                skipped += 1
                continue

            ca = CampaignAccount(
                campaign=campaign,
                account=account,
                status=initial_status,
            )
            ca.save(user=request.user, client_id=client_id)
            created_accounts.append(ca)

            # For ACTIVE campaigns: create CampaignContacts + generate activities
            # so the account appears in the playlist immediately (matches enroll_target behavior).
            if exec_service is not None:
                contacts = list(
                    Contact.objects.filter(
                        account=account,
                        client_id=client_id,
                        opted_out=False,
                    ).filter(
                        Q(email__isnull=False) | Q(phone_number__isnull=False)
                    ).exclude(
                        Q(email='') & Q(phone_number='')
                    )
                )
                for contact in contacts:
                    ca.target_contacts.add(contact)
                    CampaignContact.objects.get_or_create(
                        campaign_account=ca,
                        contact=contact,
                        defaults={
                            'client_id': client_id,
                            'status': CampaignContactStatus.IN_PROGRESS,
                        },
                    )
                    exec_service.generate_activities_for_contact(campaign, ca, contact)

        enrolled = len(created_accounts)

        audit_log(
            event='campaign_accounts_bulk_added',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign',
            target_id=str(campaign.id),
            outcome='success',
            extra={'enrolled': enrolled, 'skipped': skipped},
        )

        self._invalidate_caches(client_id)

        logger.info("campaign_accounts_bulk_added", extra={
            **ctx,
            'campaign_id': str(campaign.id),
            'enrolled': enrolled,
            'skipped': skipped,
        })

        return Response({
            'success': True,
            'data': {
                'enrolled': CampaignAccountListSerializer(created_accounts, many=True).data,
                'skipped': skipped,
                'total_requested': len(account_ids),
            },
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='bulk-remove')
    @transaction.atomic
    def bulk_remove(self, request):
        """
        Bulk remove accounts from a campaign.
        POST /campaign-accounts/bulk-remove/

        Body:
            - campaign_id: UUID
            - account_ids: [UUID]

        Only PENDING accounts can be bulk-removed.
        """
        ctx = ctx_from_request(request)
        campaign_id = request.data.get('campaign_id')
        account_ids = request.data.get('account_ids', [])

        if not campaign_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='campaign_id')
            )
        if not account_ids:
            raise StandardizedValidationError(
                CoreErrorMessages.BULK_NO_DATA.format(entity='account_ids')
            )
        

        client_id = self.get_client_id()
        self._get_campaign_scoped(campaign_id)

        removed = CampaignAccount.objects.filter(
            campaign_id=campaign_id,
            account_id__in=account_ids,
            client_id=client_id,
            status=CampaignAccountStatus.PENDING,
        ).delete()[0]

        audit_log(
            event='campaign_accounts_bulk_removed',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign',
            target_id=str(campaign_id),
            outcome='success',
            extra={'removed': removed},
        )

        self._invalidate_caches(client_id)

        logger.info("campaign_accounts_bulk_removed", extra={
            **ctx,
            'campaign_id': str(campaign_id),
            'removed': removed,
        })

        return Response({
            'success': True,
            'data': {
                'removed': removed,
                'total_requested': len(account_ids),
            },
        })

    # ==========================================================================
    # TARGETED ENROLLMENT
    # ==========================================================================

    @action(detail=False, methods=['post'], url_path='enroll-target')
    @transaction.atomic
    def enroll_target(self, request):
        """
        Enroll an account into a TARGETED campaign with immediate activity generation.
        POST /campaigns/accounts/enroll-target/

        Body:
            - campaign_id:    UUID  (required)
            - account_id:     UUID  (required)
            - type:           str   'ACCOUNT' | 'DEPARTMENT' | 'CONTACT'
            - department_id:  UUID  (optional, for DEPARTMENT type)
            - contact_ids:    list  (optional, for CONTACT type)
        """
        ctx = ctx_from_request(request)
        campaign_id  = request.data.get('campaign_id')
        account_id   = request.data.get('account_id')
        enroll_type  = request.data.get('type', 'ACCOUNT')
        department_id = request.data.get('department_id')
        contact_ids  = request.data.get('contact_ids', [])
        notes        = request.data.get('notes', '') or ''
        origin_decision_cycle_id = request.data.get('origin_decision_cycle_id')
        strict       = request.data.get('strict', False)

        if not campaign_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='campaign_id')
            )
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='account_id')
            )
        if enroll_type not in ('ACCOUNT', 'DEPARTMENT', 'CONTACT'):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='type (ACCOUNT|DEPARTMENT|CONTACT)')
            )

        client_id = self.get_client_id()
        campaign = self._get_campaign_scoped(campaign_id)

        # Validate account
        try:
            account = CompanyAccount.objects.get(id=account_id, client_id=client_id)
        except CompanyAccount.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        source_decision_cycle = None
        if origin_decision_cycle_id:
            from app_modules.decision_cycles.models import DecisionCycle
            try:
                source_decision_cycle = DecisionCycle.objects.get(
                    id=origin_decision_cycle_id,
                    client_id=client_id,
                )
            except DecisionCycle.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        # Determine status: ACTIVE campaign → IN_PROGRESS immediately
        initial_status = (
            CampaignAccountStatus.IN_PROGRESS
            if campaign.status == CampaignStatus.ACTIVE
            else CampaignAccountStatus.PENDING
        )

        # Per-campaign account cap — count only ACTIVE (non-terminal) enrollments.
        # Terminal accounts (COMPLETED/STOPPED) do not count. Re-adding an account
        # that is already active leaves the count unchanged and stays allowed;
        # a brand-new account (or the revival of a terminal one) counts as +1.
        already_active = CampaignAccount.objects.filter(
            campaign=campaign, account=account,
        ).exclude(status__in=FINAL_ACCOUNT_STATES).exists()
        if not already_active:
            active_count = CampaignAccount.objects.filter(
                campaign=campaign,
            ).exclude(status__in=FINAL_ACCOUNT_STATES).count()
            if active_count + 1 > MAX_ACCOUNTS_PER_CAMPAIGN:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.MAX_ACCOUNTS_EXCEEDED.format(
                        max=MAX_ACCOUNTS_PER_CAMPAIGN
                    )
                )

        # Get or create the CampaignAccount
        campaign_account, created = CampaignAccount.objects.get_or_create(
            campaign=campaign,
            account=account,
            client_id=client_id,
            defaults={
                'status': initial_status,
                'notes': notes or None,
            },
        )
        # If it already existed and is still PENDING on an ACTIVE campaign, promote it
        if not created and campaign.status == CampaignStatus.ACTIVE and campaign_account.status == CampaignAccountStatus.PENDING:
            campaign_account.status = CampaignAccountStatus.IN_PROGRESS
            campaign_account.save(user=request.user, client_id=client_id)

        # Update notes if provided (even on existing enrollment)
        if not created and notes:
            campaign_account.notes = notes
            campaign_account.save(user=request.user, client_id=client_id)

        if created:
            campaign_account.save(user=request.user, client_id=client_id)

        # Resolve contacts to enroll based on type
        considered_total = 0  # contacts targeted by this enrollment (per mode)
        if enroll_type == 'CONTACT':
            if not contact_ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='contact_ids')
                )

            # Check opt-out separately before reachability — dedicated error message.
            if strict and Contact.objects.filter(
                id__in=contact_ids,
                account=account,
                client_id=client_id,
                opted_out=True,
            ).exists():
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.CONTACT_OPTED_OUT
                )

            contacts = list(
                Contact.objects.filter(
                    id__in=contact_ids,
                    account=account,
                    client_id=client_id,
                    opted_out=False,
                ).filter(
                    Q(email__isnull=False) | Q(phone_number__isnull=False)
                ).exclude(
                    Q(email='') & Q(phone_number='')
                )
            )
            # Contacts considered for this enrollment (the requested ids). Anything
            # not in `contacts` was excluded for eligibility (opted-out / no reachable
            # channel), NOT because it was already active — that skip happens later.
            considered_total = len(contact_ids)
            if not contacts:
                if strict:
                    raise StandardizedValidationError(
                        CampaignModuleErrorMessages.CONTACT_NOT_REACHABLE
                    )

        elif enroll_type == 'DEPARTMENT':
            if not department_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='department_id')
                )
            contacts = list(
                Contact.objects.filter(
                    account=account,
                    client_id=client_id,
                    opted_out=False,
                    standard_department_id=department_id,
                ).filter(
                    Q(email__isnull=False) | Q(phone_number__isnull=False)
                ).exclude(
                    Q(email='') & Q(phone_number='')
                )
            )
            # Every contact of the department is considered; those not in `contacts`
            # were excluded for eligibility (opted-out / no reachable channel).
            considered_total = Contact.objects.filter(
                account=account,
                client_id=client_id,
                standard_department_id=department_id,
            ).count()
            # Store department filter on the CampaignAccount
            try:
                from app_modules.core_modules.models import StandardDepartment
                dept = StandardDepartment.objects.get(id=department_id)
                campaign_account.target_departments.add(dept)
            except Exception:
                pass
        else:  # ACCOUNT — all non opted-out contacts
            contacts = list(
                Contact.objects.filter(
                    account=account,
                    client_id=client_id,
                    opted_out=False,
                ).filter(
                    Q(email__isnull=False) | Q(phone_number__isnull=False)
                ).exclude(
                    Q(email='') & Q(phone_number='')
                )
            )
            # Every contact of the account is considered; those not in `contacts`
            # were excluded for eligibility (opted-out / no reachable channel). This
            # is what makes unreachable_count meaningful in ACCOUNT mode (where
            # contact_ids is empty), so the frontend can tell "0 reachable" apart
            # from "already active".
            considered_total = Contact.objects.filter(
                account=account,
                client_id=client_id,
            ).count()

        # Enroll contacts (always) — generate activities only when ACTIVE
        contacts_created = 0
        activities_created = 0

        from ..models import CampaignContact, CampaignContactStatus

        exec_service = (
            CampaignExecutionService(user=request.user, client_id=client_id)
            if campaign.status == CampaignStatus.ACTIVE
            else None
        )

        from ..constants import FINAL_CONTACT_STATES, CampaignType

        for contact in contacts:
            # Skip contacts that already have open planned activities
            has_open_activities = Activity.objects.filter(
                campaign=campaign,
                campaign_contact__contact=contact,
                status=ActivityStatus.PLANNED,
            ).exists()
            if has_open_activities:
                continue

            # Always link contact to the campaign account
            campaign_account.target_contacts.add(contact)

            campaign_contact, cc_created = CampaignContact.objects.get_or_create(
                campaign_account=campaign_account,
                contact=contact,
                defaults={
                    'client_id': client_id,
                    'status': (
                        CampaignContactStatus.IN_PROGRESS
                        if campaign.status == CampaignStatus.ACTIVE
                        else CampaignContactStatus.PENDING
                    ),
                },
            )

            # TARGETED only: reactivate contacts that have already completed
            # or been stopped in a previous sequence cycle.
            # This is the core re-enrollment mechanic for TARGETED campaigns —
            # without reactivate(), activities_generated=True blocks new generation.
            if (
                not cc_created
                and campaign.campaign_type == CampaignType.TARGETED
                and campaign_contact.status in FINAL_CONTACT_STATES
            ):
                campaign_contact.reactivate(user=request.user)

            contacts_created += 1

            # Generate activities only if campaign is already running
            if exec_service is not None:
                count = exec_service.generate_activities_for_contact(
                    campaign, campaign_account, contact,
                    source_decision_cycle=source_decision_cycle,
                )
                activities_created += count if isinstance(count, int) else 0
        
        # If no contacts were enrolled and the CampaignAccount was just created,
        # delete it — an account with no reachable contacts must not block
        # campaign completion or pollute the accounts list.
        if contacts_created == 0 and created:
            campaign_account.delete()
            return Response({
                'success': True,
                'data': {
                    'campaign_account': None,
                    'contacts_enrolled': 0,
                    'activities_created': 0,
                    'contacts_skipped': len(contact_ids) if contact_ids else 0,
                    'unreachable_count': max(0, considered_total - len(contacts)),
                    'skip_reason': 'no_reachable_contacts',
                    'warning': CampaignModuleErrorMessages.CONTACT_NOT_REACHABLE,
                },
            }, status=status.HTTP_201_CREATED)

        # 1A fix: re-chasing a contact revives the parent account. If this enroll
        # left the account with at least one non-final contact, re-derive its
        # stored status upward (STOPPED/COMPLETED → IN_PROGRESS). TARGETED-only and
        # guarded inside revive_if_active — a strict no-op on OUTBOUND.
        campaign_account.revive_if_active(user=request.user)

        audit_log(
            event='campaign_target_enrolled',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign_account',
            target_id=str(campaign_account.id),
            outcome='success',
            extra={
                'enroll_type': enroll_type,
                'contacts_enrolled': contacts_created,
                'activities_created': activities_created,
                'origin_decision_cycle_id': str(origin_decision_cycle_id) if origin_decision_cycle_id else None,
            },
        )

        self._invalidate_caches(client_id)

        logger.info("campaign_target_enrolled", extra={
            **ctx,
            'campaign_id': str(campaign.id),
            'account_id': str(account.id),
            'enroll_type': enroll_type,
            'contacts_enrolled': contacts_created,
            'activities_created': activities_created,
        })

        output = CampaignAccountDetailSerializer(campaign_account, context={'request': request})

        # Contacts filtered out due to no email/phone or opted-out (not the same as
        # contacts skipped because they already had open activities). Computed from
        # considered_total for EVERY mode (incl. ACCOUNT, where contact_ids is empty)
        # so the frontend can distinguish "0 reachable" from "already active".
        unreachable_count = max(0, considered_total - len(contacts))

        return Response({
            'success': True,
            'data': {
                'campaign_account': output.data,
                'contacts_enrolled': contacts_created,
                'activities_created': activities_created,
                'contacts_skipped': len(contact_ids) - contacts_created if contact_ids else 0,
                'unreachable_count': unreachable_count,
                'skip_reason': (
                    'no_reachable_contacts'
                    if contacts_created == 0 and contact_ids and not strict
                    else None
                ),
                # Warning surfaced to frontend when contacts were silently filtered
                'warning': (
                    CampaignModuleErrorMessages.CONTACT_NOT_REACHABLE
                    if unreachable_count > 0 and not strict
                    else None
                ),
            },
        }, status=status.HTTP_201_CREATED)


    # ==========================================================================
    # LIST ACTIONS
    # ==========================================================================

    @action(detail=False, methods=['get'], url_path='by-campaign')
    def by_campaign(self, request):
        """
        Get accounts for a specific campaign.
        GET /campaign-accounts/by-campaign/?campaign_id={uuid}
        """
        ctx = ctx_from_request(request)
        campaign_id = request.query_params.get('campaign_id')

        if not campaign_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='campaign_id')
            )

        logger.info("campaign_accounts_by_campaign_requested", extra={
            **ctx, 'campaign_id': campaign_id,
        })

        queryset = self.get_queryset().filter(campaign_id=campaign_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CampaignAccountListSerializer(
                page, many=True, context={'request': request}
            )
            return Response({
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                },
            })

        serializer = CampaignAccountListSerializer(
            queryset, many=True, context={'request': request}
        )
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data),
            },
        })

    # ==========================================================================
    # PRIVATE HELPERS
    # ==========================================================================

    def _get_campaign_scoped(self, campaign_id):
        from django.db.models import Q
        from core.exceptions import StandardizedPermissionDenied
        from core.error_messages import CoreErrorMessages
        from permissions.compat import get_auth_ctx

        client_id = self.get_client_id()
        user = self.request.user

        try:
            campaign = Campaign.objects.get(id=campaign_id, client_id=client_id)
        except Campaign.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        # Admins have full client scope — skip owner/executor check.
        ctx = get_auth_ctx(self.request)
        is_admin = ctx.is_superuser or any(
            isinstance(r, dict) and r.get('is_admin') for r in ctx.roles
        )
        if is_admin:
            return campaign

        if not Campaign.objects.filter(
            id=campaign_id,
            client_id=client_id,
        ).filter(
            Q(owner=user) | Q(executor=user)
        ).exists():
            raise StandardizedPermissionDenied(CoreErrorMessages.PERMISSION_DENIED)

        return campaign

    def _audit_status_change(self, request, instance, transition_result):
        """Emit audit log for status transitions."""
        audit_log(
            event='campaign_account_status_changed',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_account',
            target_id=str(instance.id),
            outcome='success',
            extra={
                'from_status': transition_result.get('from_status'),
                'to_status': transition_result.get('to_status'),
            },
        )