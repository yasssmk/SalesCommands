# apps/campaign/models/campaign_target.py

from django.db import models
from django.utils import timezone
from typing import Dict, Optional
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignErrorMessages
from apps.campaign.utils.target_state_machine import TargetStateMachine
from django.db import transaction


class CampaignTarget(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Links ONE target (account OR contact OR lead OR opportunity) to a campaign
    A campaign can have many targets of different types
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        CALLBACK_PENDING = 'CALLBACK_PENDING', _('Callback Pending') 
        COMPLETED = 'COMPLETED', _('Completed')
        STOPPED = 'STOPPED', _('Stopped')
    
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.CASCADE,
        related_name='targets',
        verbose_name=_('Campaign')
    )
    
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Account'),
        blank=True,
        null=True
    )
    
    contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Contact'),
        blank=True,
        null=True
    )
    
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Lead'),
        blank=True,
        null=True
    )
    
    # New field for opportunity as a target
    target_opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='targeted_by_campaigns',
        verbose_name=_('Target Opportunity'),
        blank=True,
        null=True
    )
    
    # Status tracking
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Status')
    )
    
    activities_generated = models.BooleanField(
        default=False,
        verbose_name=_('Activities Generated')
    )

    callback_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Callback Date'),
        help_text=_('Date when contact requested to be called back')
    )

    no_answer_count = models.IntegerField(
        default=0,
        verbose_name=_('No Answer Count'),
        help_text=_('Number of times contact did not answer')
    )
        
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    # 'linked_opportunity' is used to track if this target is linked to an opportunity
    linked_opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.SET_NULL,
        related_name='linked_campaign_targets',
        null=True,
        blank=True,
        verbose_name=_('Linked Opportunity')
    )
    
    class Meta:
        verbose_name = _('Campaign Target')
        verbose_name_plural = _('Campaign Targets')
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['lead', 'status']),
            models.Index(fields=['target_opportunity', 'status']),
            models.Index(fields=['activities_generated']),
        ]
        constraints = [
            # Ensure unique account per campaign
            models.UniqueConstraint(
                fields=['campaign', 'account'],
                condition=models.Q(contact__isnull=True, lead__isnull=True, target_opportunity__isnull=True),
                name='unique_campaign_account_only'
            ),
            # Ensure unique contact per campaign
            models.UniqueConstraint(
                fields=['campaign', 'contact'],
                condition=models.Q(contact__isnull=False),
                name='unique_campaign_contact'
            ),
            # Ensure unique lead per campaign
            models.UniqueConstraint(
                fields=['campaign', 'lead'],
                condition=models.Q(lead__isnull=False),
                name='unique_campaign_lead'
            ),
            # Ensure unique opportunity per campaign
            models.UniqueConstraint(
                fields=['campaign', 'target_opportunity'],
                condition=models.Q(target_opportunity__isnull=False),
                name='unique_campaign_opportunity'
            )
        ]

    def __str__(self):
        if self.contact:
            return f"{self.campaign.name} - Contact: {self.contact.first_name} {self.contact.last_name} ({self.get_status_display()})"
        elif self.lead:
            return f"{self.campaign.name} - Lead: {self.lead.title} ({self.get_status_display()})"
        elif self.target_opportunity:
            return f"{self.campaign.name} - Opportunity: {self.target_opportunity.name} ({self.get_status_display()})"
        elif self.account:
            return f"{self.campaign.name} - Account: {self.account.company_name} ({self.get_status_display()})"
        return f"{self.campaign.name} - No Target ({self.get_status_display()})"
    
    def clean(self):
        """Validate that exactly one target type is set using standardized validation"""
        super().clean()
        
        try:
            target_count = sum([
                bool(self.account),
                bool(self.contact),
                bool(self.lead),
                bool(self.target_opportunity)
            ])
            
            if target_count == 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field="Target (one of: account, contact, lead, or opportunity)"
                    )
                )
            
            if target_count > 1:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Target selection (only one target type can be specified per campaign target)"
                    )
                )
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target validation failed")
            )
    
    def save(self, *args, **kwargs):
        """Save with standardized validation"""
        try:
            # Run clean validation first
            self.full_clean()
            super().save(*args, **kwargs)
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target save failed")
            )
    
    def get_target_type(self):
        """Return the type of target"""
        try:
            if self.contact:
                return 'contact'
            elif self.lead:
                return 'lead'
            elif self.target_opportunity:
                return 'opportunity'
            elif self.account:
                return 'account'
            return None
        except Exception:
            return None
    
    def get_target(self):
        """Return the actual target object"""
        try:
            if self.contact:
                return self.contact
            elif self.lead:
                return self.lead
            elif self.target_opportunity:
                return self.target_opportunity
            elif self.account:
                return self.account
            return None
        except Exception:
            return None
    
    def get_target_account(self):
        """Get the account associated with this target"""
        try:
            if self.account:
                return self.account
            elif self.contact:
                return self.contact.account
            elif self.lead:
                return self.lead.account
            elif self.target_opportunity:
                return self.target_opportunity.account
            return None
        except Exception:
            return None
    
    def mark_activities_generated(self, save=True):
        """Mark that activities have been generated for this target"""
        try:
            self.activities_generated = True
            
            if save:
                self.save()
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to mark activities as generated")
            )


    def update_status(self, new_status, trigger=None, notes=None, user=None, 
                save=True, validate_consistency=False, source='manual'):
        """
        ✅ CORRIGÉ : Ordre des validations et debugging State Machine
        """
        try:
            old_status = self.status
            old_status_display = self.get_status_display()
            
            # 1. Basic status validation (existing logic - always applied)
            valid_statuses = [choice[0] for choice in self.Status.choices]
            if new_status not in valid_statuses:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Status (must be one of: {', '.join(valid_statuses)})"
                    )
                )
            
            # 2. No change needed (check early)
            if old_status == new_status:
                return {
                    'status_updated': False,
                    'old_status': old_status,
                    'new_status': new_status,
                    'source': source,
                    'state_machine_used': False,
                    'no_change_needed': True,
                    'timestamp': timezone.now().isoformat()
                }
            
            # 3. Determine if State Machine validation should be used
            use_state_machine = source in ['manual', 'business_result']

            # 4. ✅ STATE MACHINE VALIDATION (AVANT consistency validation)
            if use_state_machine:
                try:
                    TargetStateMachine.validate_transition(
                        from_state=old_status,
                        to_state=new_status,
                        trigger=trigger
                    )
                except Exception as state_machine_error:

                    raise  # Re-raise l'exception State Machine


            # 5. Consistency validation (existing logic - applied when requested)
            if validate_consistency:
                expected_status = self._calculate_expected_status()
                if expected_status and new_status != expected_status:

                    raise StandardizedValidationError(
                        CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(
                            current_state=f"Status '{new_status}' inconsistent with activities (expected: '{expected_status}')"
                        )
                    )

            
            # 6. Perform the transition
            with transaction.atomic():
                self.status = new_status
                
                # Enhanced transition notes with source tracking
                if notes or source != 'auto_sync':
                    transition_note = f"[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Status: {old_status} → {new_status}"
                    
                    # Add source information
                    if source == 'manual':
                        transition_note += " (manual change)"
                    elif source == 'business_result':
                        transition_note += " (business result)"
                    elif source == 'auto_sync':
                        transition_note += " (auto-sync)"
                    
                    # Add trigger information
                    if trigger:
                        transition_note += f" [trigger: {trigger}]"
                    
                    # Add user notes
                    if notes:
                        transition_note += f": {notes}"
                    
                    # Append to existing notes
                    if self.notes:
                        self.notes += f"\n{transition_note}"
                    else:
                        self.notes = transition_note
                
                if save:
                    self.save()
                    
                # Enhanced logging with source tracking
                self._log_status_transition(
                    old_status=old_status,
                    new_status=new_status,
                    trigger=trigger,
                    user=user,
                    notes=notes,
                    source=source
                )
            
            return {
                'status_updated': True,
                'old_status': old_status,
                'old_status_display': old_status_display,
                'new_status': new_status,
                'new_status_display': self.get_status_display(),
                'trigger': trigger,
                'source': source,
                'state_machine_used': use_state_machine,
                'transition_valid': True,
                'timestamp': timezone.now().isoformat(),
                'updated_by': user.id if user else None
            }
            
        except StandardizedValidationError:
            # Re-raise validation errors from State Machine or existing logic
            raise
        except Exception as e:

            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_STATUS_UPDATE_FAILED.format(reason=str(e))
            )

    def _log_status_transition(self, old_status: str, new_status: str, 
                            trigger: str = None, user=None, notes: str = None, 
                            source: str = 'manual'):
        """
        Enhanced logging with source tracking and State Machine information
        """
        try:
            log_entry = {
                'target_id': self.id,
                'campaign_id': self.campaign.id,
                'target_type': self.get_target_type(),
                'old_status': old_status,
                'new_status': new_status,
                'trigger': trigger,
                'source': source,
                'user_id': user.id if user else None,
                'notes': notes,
                'state_machine_used': source in ['manual', 'business_result'],
                'is_final_state': TargetStateMachine.is_final_state(new_status),
                'allowed_next_transitions': TargetStateMachine.get_allowed_transitions(new_status),
                'timestamp': timezone.now().isoformat()
            }
            
            # TODO: Replace with proper audit logging system
            print(f"TARGET_STATUS_TRANSITION: {log_entry}")
            
        except Exception as e:
            # Don't fail the transaction for logging errors
            print(f"Failed to log status transition: {str(e)}")
            
    
    def _calculate_expected_status(self) -> Optional[str]:
        """
        Calcule le statut attendu basé sur les activités associées
        ADAPTÉ aux 5 statuts : PENDING, IN_PROGRESS, CALLBACK_PENDING, COMPLETED, STOPPED
        
        Returns:
            Optional[str]: Statut attendu ou None si indéterminable
        """
        from apps.activities.models import Activity
        
        activities = Activity.objects.filter(campaign_info__campaign_target=self)
        if not activities.exists():
            return None
        
        # Récupérer les statuts et notes
        activity_data = activities.values_list('status', 'outcome_notes')
        statuses = [data[0] for data in activity_data]
        notes = [data[1] or '' for data in activity_data]
        
        # ✅ LOGIQUE AVEC 5 STATUTS 

        # 1. Vérifier si callback demandé (priorité haute)
        has_callback = any(
            'callback' in note.lower() 
            for note in notes
        )
        if has_callback:
            return self.Status.CALLBACK_PENDING
        
        # 2. Vérifier si résultat business positif (meeting, lead, etc.)
        has_positive_result = any(
            ('meeting' in note.lower() and 'scheduled' in note.lower()) or
            ('lead' in note.lower() and 'created' in note.lower()) or
            ('opportunity' in note.lower() and 'created' in note.lower()) or
            ('successful' in note.lower())
            for note in notes
        )
        if has_positive_result:
            return self.Status.COMPLETED
        
        # 3. Vérifier si contact pas intéressé
        has_not_interested = any(
            'not interested' in note.lower() or 'unsubscribe' in note.lower()
            for note in notes
        )
        if has_not_interested:
            return self.Status.STOPPED
        
        # 4. Vérifier si aucune activité n'a encore commencé
        completed_count = statuses.count(Activity.Status.COMPLETED)
        cancelled_count = statuses.count(Activity.Status.CANCELLED)
        planned_count = statuses.count(Activity.Status.PLANNED)
        total_count = len(statuses)
        
        # Si toutes les activités sont PLANNED = PENDING (Option A)
        if planned_count == total_count:
            return self.Status.PENDING
        
        # Si toutes les activités sont annulées = STOPPED
        if cancelled_count == total_count:
            return self.Status.STOPPED
        
        # Si au moins une activité complétée = IN_PROGRESS
        if completed_count > 0:
            return self.Status.IN_PROGRESS
        
        # Par défaut, si mix d'activités (some planned, some cancelled) = IN_PROGRESS
        return self.Status.IN_PROGRESS
    
    def sync_status_with_activities(self, save=True) -> bool:
        """
        Synchronise automatiquement le statut avec l'état des activités
        FIXED: Uses enhanced update_status with source='auto_sync' only
        
        Args:
            save (bool): Si True, sauvegarde automatiquement
            
        Returns:
            bool: True si le statut a changé, False sinon
        """
        try:
            expected_status = self._calculate_expected_status()
            if not expected_status:
                return False  # Pas d'activités, pas de changement
            
            if self.status != expected_status:
                # 🔧 FIX: Use update_status ONLY, remove direct modification
                result = self.update_status(
                    new_status=expected_status,
                    trigger='activity_sync',  # Informational trigger
                    notes='Auto-synchronized with activity status',
                    source='auto_sync',  # 🔑 This bypasses State Machine validation
                    save=save,
                    validate_consistency=False  # Skip consistency check since we're fixing it
                )
                
                return result.get('status_updated', False)
            
            return False
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_STATUS_SYNC_FAILED.format(
                    reason=f"Failed to sync status for target {self.id}: {str(e)}"
                )
            )
        
    @classmethod
    def sync_all_targets_with_campaign_status(cls, campaign, new_campaign_status: str, 
                                            old_campaign_status: str = None,
                                            user=None, notes: str = None) -> Dict:
        """
        ✅ SIMPLIFIÉ: Synchronise toutes les targets avec le trigger 'campaign_status_change'
        Utilise la nouvelle logique simplifiée d'auto_update_status_if_needed
        
        Args:
            campaign: Campagne dont les targets doivent être synchronisées
            new_campaign_status: Nouveau statut de la campagne ('ACTIVE', 'PAUSED', etc.)
            old_campaign_status: Ancien statut (optionnel, pour logging)
            user: Utilisateur déclenchant la synchronisation
            notes: Notes additionnelles
            
        Returns:
            Dict: Résumé de la synchronisation avec compteurs par résultat
        """
        try:
            # Import local pour éviter la circularité
            from apps.campaign.utils.target_state_machine import TargetStateMachine
            
            # ✅ RÉCUPÉRER TOUTES LES TARGETS de la campagne
            all_targets = cls.objects.filter(campaign=campaign)
            
            # Filtrer seulement les targets non-finales (éviter de modifier COMPLETED/STOPPED)
            syncable_targets = [
                target for target in all_targets 
                if not TargetStateMachine.is_final_state(target.status)
            ]
            
            # Compteurs pour le rapport
            results_summary = {
                'targets_processed': 0,
                'targets_updated': 0,
                'targets_skipped': 0,
                'targets_failed': 0,
                'final_targets_ignored': len(all_targets) - len(syncable_targets),
                'details': []
            }
            
            # ✅ APPLIQUER auto_update_status_if_needed avec trigger 'campaign_status_change'
            for target in syncable_targets:
                try:
                    results_summary['targets_processed'] += 1
                    
                    # ✅ UTILISER LE NOUVEAU TRIGGER SPÉCIFIQUE
                    update_result = target.auto_update_status_if_needed(
                        user=user, 
                        trigger_type='campaign_status_change'
                    )
                    
                    # Traiter le résultat
                    if update_result.get('action_taken') == 'status_updated':
                        results_summary['targets_updated'] += 1
                        results_summary['details'].append({
                            'target_id': target.id,
                            'target_type': target.get_target_type(),
                            'old_status': update_result.get('old_status'),
                            'new_status': update_result.get('new_status'),
                            'sync_reason': update_result.get('sync_reason'),
                            'trigger_used': update_result.get('trigger'),
                            'success': True
                        })
                    else:
                        results_summary['targets_skipped'] += 1
                        results_summary['details'].append({
                            'target_id': target.id,
                            'target_type': target.get_target_type(),
                            'current_status': target.status,
                            'reason': update_result.get('reason', 'No change needed'),
                            'action_taken': update_result.get('action_taken'),
                            'success': True,
                            'skipped': True
                        })
                    
                except StandardizedValidationError as validation_error:
                    results_summary['targets_failed'] += 1
                    results_summary['details'].append({
                        'target_id': target.id,
                        'target_type': target.get_target_type(),
                        'error': str(validation_error),
                        'error_type': 'validation_error',
                        'success': False
                    })
                    
                    # Log l'erreur mais continuer avec les autres targets
                    print(f"VALIDATION ERROR syncing target {target.id}: {validation_error}")
                    
                except Exception as target_error:
                    results_summary['targets_failed'] += 1
                    results_summary['details'].append({
                        'target_id': target.id,
                        'target_type': target.get_target_type(),
                        'error': str(target_error),
                        'error_type': 'unexpected_error',
                        'success': False
                    })
                    
                    # Log l'erreur mais continuer avec les autres targets
                    print(f"UNEXPECTED ERROR syncing target {target.id}: {target_error}")
            
            # ✅ RAPPORT FINAL simplifié
            final_result = {
                'action_taken': 'campaign_status_change_sync',
                'campaign_id': campaign.id,
                'campaign_status_change': f"{old_campaign_status or 'Unknown'} → {new_campaign_status}",
                'sync_method': 'trigger_campaign_status_change',
                'trigger_type': 'campaign_status_change',
                'total_targets_in_campaign': len(all_targets),
                'syncable_targets': len(syncable_targets),
                'final_targets_ignored': results_summary['final_targets_ignored'],
                'targets_processed': results_summary['targets_processed'],
                'targets_updated': results_summary['targets_updated'],
                'targets_skipped': results_summary['targets_skipped'],
                'targets_failed': results_summary['targets_failed'],
                'success_rate': round((results_summary['targets_updated'] / max(1, results_summary['targets_processed'])) * 100, 1),
                'has_failures': results_summary['targets_failed'] > 0,
                'details': results_summary['details'] if results_summary['targets_failed'] > 0 else f"{results_summary['targets_updated']} targets synchronized via campaign status change trigger",
                'timestamp': timezone.now().isoformat()
            }
            
            print(f"✅ CAMPAIGN STATUS SYNC: {final_result['targets_updated']}/{final_result['targets_processed']} targets updated for campaign {campaign.id} → {new_campaign_status}")
            
            return final_result
            
        except StandardizedValidationError:
            # ✅ Re-raise les erreurs de validation standardisées
            raise
        except Exception as e:
            # ✅ Convertir erreurs inattendues en format standardisé
            raise StandardizedValidationError(
                CampaignErrorMessages.BULK_OPERATION_FAILED.format(
                    operation=f"campaign status change synchronization for campaign {getattr(campaign, 'id', 'unknown')}: {str(e)}"
                )
            )
    
    def get_activities_summary(self) -> Dict:
        """
        Obtient un résumé des activités pour diagnostic et debugging
        
        Returns:
            Dict: Résumé complet des activités associées
        """
        from apps.activities.models import Activity
        
        activities = Activity.objects.filter(campaign_info__campaign_target=self)
        
        summary = {
            'target_id': self.id,
            'target_type': self.get_target_type(),
            'current_status': self.status,
            'total_activities': activities.count(),
            'by_status': {},
            'by_type': {},
            'has_meeting_scheduled': False,
            'last_completed_activity': None,
            'expected_status': self._calculate_expected_status()
        }
        
        # Compter par statut d'activité
        for status_choice in Activity.Status.choices:
            status_code = status_choice[0]
            count = activities.filter(status=status_code).count()
            summary['by_status'][status_code] = count
        
        # Compter par type d'activité
        for type_choice in Activity.ActivityType.choices:
            type_code = type_choice[0]
            count = activities.filter(activity_type=type_code).count()
            if count > 0:
                summary['by_type'][type_code] = count
        
        # Vérifier présence de meeting
        meeting_notes = activities.filter(
            models.Q(outcome_notes__icontains='meeting') & 
            models.Q(outcome_notes__icontains='scheduled')
        ).exists()
        summary['has_meeting_scheduled'] = meeting_notes
        
        # Dernière activité complétée
        last_activity = activities.filter(
            status=Activity.Status.COMPLETED
        ).order_by('-completed_at').first()
        
        if last_activity:
            summary['last_completed_activity'] = {
                'id': last_activity.id,
                'type': last_activity.activity_type,
                'completed_at': last_activity.completed_at.isoformat() if last_activity.completed_at else None,
                'notes': last_activity.outcome_notes or ''
            }
        
        return summary
    
    def validate_status_consistency(self, check_state_machine=True) -> Dict:
        """
        Enhanced validation with optional State Machine checks
        
        Args:
            check_state_machine: If True, also validates State Machine compliance
            
        Returns:
            Dict: Enhanced validation report
        """
        expected_status = self._calculate_expected_status()
        current_status = self.status
        
        is_consistent = (
            expected_status is None or  # No activities = no constraint
            current_status == expected_status
        )
        
        # NEW: Optional State Machine validation
        state_machine_issues = []
        if check_state_machine and self.notes:
            # Check if previous transitions were valid
            history = self.get_status_history_summary()
            for transition in history['transitions']:
                from_state = transition['from_status']
                to_state = transition['to_status']
                if not TargetStateMachine.can_transition(from_state, to_state):
                    state_machine_issues.append({
                        'invalid_transition': f"{from_state} → {to_state}",
                        'timestamp': transition['timestamp']
                    })
        
        return {
            'target_id': self.id,
            'is_consistent': is_consistent,
            'current_status': current_status,
            'expected_status': expected_status,
            'needs_sync': not is_consistent,
            'activities_count': self.get_activities_summary()['total_activities'],
            'state_machine_compliant': len(state_machine_issues) == 0,
            'state_machine_issues': state_machine_issues,
            'validation_timestamp': timezone.now().isoformat()
        }

    def auto_update_status_if_needed(self, user=None, trigger_type=None) -> Dict:
        """
        ✅ SIMPLIFIÉ: Auto-update avec triggers spécifiques et logiques distinctes
        
        Args:
            user: User triggering the auto-update (for audit)
            trigger_type: 'campaign_status_change' ou 'activity_result'
            
        Returns:
            Dict: Update report avec action prise
        """
        try:
            # 1. ✅ VÉRIFIER SI TARGET DÉJÀ DANS UN ÉTAT FINAL (pour tous les triggers)
            if TargetStateMachine.is_final_state(self.status):
                return {
                    'target_id': self.id,
                    'action_taken': 'no_change_needed',
                    'reason': 'Target in final state',
                    'current_status': self.status,
                    'is_final_state': True,
                    'trigger_type': trigger_type,
                    'timestamp': timezone.now().isoformat()
                }
            
            # 2. ✅ ROUTER SELON LE TRIGGER SPÉCIFIQUE
            if trigger_type == 'campaign_status_change':
                return self._handle_campaign_status_change_trigger(user)
                
            elif trigger_type == 'activity_result':
                return self._handle_activity_result_trigger(user)
                
            else:
                # Fallback pour compatibilité - utilise trigger campagne par défaut
                return self._handle_campaign_status_change_trigger(user)
                
        except StandardizedValidationError:
            # ✅ Re-raise les erreurs de validation standardisées
            raise
        except Exception as e:
            # ✅ Convertir erreurs inattendues en format standardisé
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_STATUS_UPDATE_FAILED.format(
                    reason=f"Auto-update failed for target {self.id}: {str(e)}"
                )
            )
    
    def _handle_campaign_status_change_trigger(self, user=None) -> Dict:
        """
        ✅ NOUVEAU: Gère uniquement les changements PENDING ↔ IN_PROGRESS selon statut campagne
        Ignore complètement les targets en CALLBACK_PENDING, COMPLETED, STOPPED
        
        Args:
            user: User for audit
            
        Returns:
            Dict: Update result
        """
        try:
            campaign_status = self.campaign.status
            current_target_status = self.status
            
            # ✅ SEULEMENT pour targets PENDING ou IN_PROGRESS
            if current_target_status not in [self.Status.PENDING, self.Status.IN_PROGRESS]:
                return {
                    'target_id': self.id,
                    'action_taken': 'no_change_needed',
                    'reason': f'Target status {current_target_status} not affected by campaign status changes',
                    'campaign_status': campaign_status,
                    'target_status': current_target_status,
                    'trigger_type': 'campaign_status_change',
                    'timestamp': timezone.now().isoformat()
                }
            
            # ✅ LOGIQUE SIMPLE : ACTIVE → IN_PROGRESS, autres → PENDING
            if campaign_status == 'ACTIVE':
                expected_status = self.Status.IN_PROGRESS
                trigger = 'campaign_activated' if current_target_status == self.Status.PENDING else 'campaign_resumed'
                notes = "Campaign is active"
                
            elif campaign_status in ['PAUSED', 'DRAFT']:
                expected_status = self.Status.PENDING
                trigger = 'campaign_paused' if campaign_status == 'PAUSED' else 'campaign_draft'
                notes = f"Campaign is {campaign_status.lower()}"
                
            else:
                # Pour COMPLETED, CANCELLED, etc. → pas de changement forcé
                return {
                    'target_id': self.id,
                    'action_taken': 'no_change_needed',
                    'reason': f'No forced alignment for campaign status {campaign_status}',
                    'campaign_status': campaign_status,
                    'target_status': current_target_status,
                    'trigger_type': 'campaign_status_change',
                    'timestamp': timezone.now().isoformat()
                }
            
            # ✅ APPLIQUER LE CHANGEMENT SI NÉCESSAIRE
            if current_target_status == expected_status:
                return {
                    'target_id': self.id,
                    'action_taken': 'no_change_needed',
                    'reason': 'Target already in correct status for campaign state',
                    'campaign_status': campaign_status,
                    'target_status': current_target_status,
                    'trigger_type': 'campaign_status_change',
                    'timestamp': timezone.now().isoformat()
                }
            
            # ✅ FORCER LE CHANGEMENT avec source='campaign_change'
            update_result = self.update_status(
                new_status=expected_status,
                trigger=trigger,
                notes=notes,
                user=user,
                source='campaign_change',  # Force l'alignement
                save=True,
                validate_consistency=False
            )
            
            # Enrichir la réponse
            update_result['action_taken'] = 'status_updated'
            update_result['sync_reason'] = 'campaign_status_alignment'
            update_result['trigger_type'] = 'campaign_status_change'
            update_result['campaign_status'] = campaign_status
            
            return update_result
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_STATUS_SYNC_FAILED.format(
                    reason=f"Campaign status sync failed for target {self.id}: {str(e)}"
                )
            )

    def _handle_activity_result_trigger(self, user=None) -> Dict:
        """
        ✅ NOUVEAU: Gère uniquement la synchronisation basée sur les résultats d'activités
        Peut faire passer vers CALLBACK_PENDING, COMPLETED, STOPPED selon les activités
        
        Args:
            user: User for audit
            
        Returns:
            Dict: Update result
        """
        try:
            # ✅ UTILISER LA LOGIQUE EXISTANTE DE VALIDATION DES ACTIVITÉS
            validation = self.validate_status_consistency()
            
            if validation['needs_sync']:
                old_status = self.status
                
                # ✅ UTILISER sync_status_with_activities EXISTANTE avec source='auto_sync'
                status_changed = self.sync_status_with_activities(save=True)
                
                if status_changed:
                    return {
                        'target_id': self.id,
                        'action_taken': 'status_updated',
                        'sync_reason': 'activities_based_sync',
                        'old_status': old_status,
                        'new_status': self.status,
                        'was_inconsistent': True,
                        'state_machine_used': False,  # sync_status_with_activities utilise source='auto_sync'
                        'trigger_type': 'activity_result',
                        'triggered_by_user': user.id if user else None,
                        'timestamp': timezone.now().isoformat()
                    }
                else:
                    return {
                        'target_id': self.id,
                        'action_taken': 'sync_attempted_no_change',
                        'reason': 'Activities sync attempted but no change occurred',
                        'trigger_type': 'activity_result',
                        'timestamp': timezone.now().isoformat()
                    }
            else:
                return {
                    'target_id': self.id,
                    'action_taken': 'no_change_needed',
                    'reason': 'Target status consistent with activities',
                    'status': self.status,
                    'was_inconsistent': False,
                    'is_state_machine_compliant': validation.get('state_machine_compliant', True),
                    'trigger_type': 'activity_result',
                    'timestamp': timezone.now().isoformat()
                }
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_STATUS_UPDATE_FAILED.format(
                    reason=f"Activity result sync failed for target {self.id}: {str(e)}"
                )
            )
        
    
    def _sync_with_campaign_status(self, campaign_status: str, user=None) -> Dict:
        """
        ✅ NOUVEAU : Synchronisation basée sur le statut de campagne
        Utilise les méthodes centralisées pour éviter doublons
        """
        current_target_status = self.status
        
        try:
            # ✅ CAMPAGNE ACTIVE → targets non-finaux doivent être IN_PROGRESS
            if campaign_status == 'ACTIVE':
                if current_target_status == self.Status.PENDING:
                    # PENDING → IN_PROGRESS car campagne active
                    update_result = self.mark_as_active_due_to_campaign(
                        campaign_status_trigger='campaign_activated',
                        notes="Campaign is now active",
                        user=user
                    )
                    update_result['sync_reason'] = 'campaign_active_pending_to_progress'
                    return update_result
                    
                elif current_target_status == self.Status.CALLBACK_PENDING:
                    # CALLBACK_PENDING → IN_PROGRESS car campagne active (callback expired)
                    update_result = self.mark_as_active_due_to_campaign(
                        campaign_status_trigger='campaign_resumed',
                        notes="Campaign active, resuming from callback",
                        user=user
                    )
                    update_result['sync_reason'] = 'campaign_active_callback_to_progress'
                    return update_result
            
            # ✅ CAMPAGNE EN PAUSE → targets IN_PROGRESS peuvent être pausés
            elif campaign_status == 'PAUSED':
                if current_target_status == self.Status.IN_PROGRESS:
                    # IN_PROGRESS → PENDING (pause temporaire)
                    update_result = self.handle_campaign_pause(
                        notes="Campaign paused",
                        user=user
                    )
                    update_result['sync_reason'] = 'campaign_paused_progress_to_pending'
                    return update_result
            
            # ✅ CAMPAGNE DRAFT → targets doivent rester PENDING
            elif campaign_status in ['DRAFT']:
                if current_target_status == self.Status.IN_PROGRESS:
                    # Cas rare : campaign remise en DRAFT, targets doivent revenir PENDING
                    update_result = self.update_status(
                        new_status=self.Status.PENDING,
                        trigger='campaign_reactivated',  # Placeholder trigger
                        notes="Campaign returned to draft status",
                        user=user,
                        source='business_result'
                    )
                    update_result['sync_reason'] = 'campaign_draft_progress_to_pending'
                    return update_result
            
            # ✅ CAMPAGNE TERMINÉE → laisser targets dans leur état
            elif campaign_status in ['COMPLETED', 'CANCELLED']:
                # Pas de changement automatique nécessaire
                pass
            
            # ✅ PAS DE SYNCHRONISATION NÉCESSAIRE
            return {
                'target_id': self.id,
                'action_taken': 'no_sync_needed',
                'reason': f'No sync needed for campaign status {campaign_status} and target status {current_target_status}',
                'campaign_status': campaign_status,
                'target_status': current_target_status,
                'timestamp': timezone.now().isoformat()
            }
            
        except StandardizedValidationError:
            # ✅ Re-raise les erreurs de validation standardisées
            raise
        except Exception as e:
            # ✅ Convertir erreurs inattendues en format standardisé
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_STATUS_SYNC_FAILED.format(
                    reason=f"Campaign sync failed for target {self.id}: {str(e)}"
                )
            )

    def mark_as_completed(self, reason: str = 'manual_completion', notes: str = None, user=None) -> dict:
        """
        Mark target as completed with appropriate business trigger
        
        Args:
            reason: Completion reason - maps to State Machine triggers
            notes: Optional completion notes
            user: User marking as completed
            
        Returns:
            dict: Update result from enhanced update_status()
        """
        # Map reasons to State Machine triggers
        trigger_mapping = {
            'manual_completion': 'manual_completion',
            'successful_activity': 'successful_activity', 
            'meeting_scheduled': 'meeting_scheduled',
            'lead_created': 'lead_created',
            'opportunity_created': 'opportunity_created'
        }
        
        trigger = trigger_mapping.get(reason, 'manual_completion')
        completion_notes = f"Target completed: {reason}"
        if notes:
            completion_notes += f" - {notes}"
        
        return self.update_status(
            new_status=self.Status.COMPLETED,
            trigger=trigger,
            notes=completion_notes,
            user=user,
            source='business_result'
        )

    def mark_as_stopped(self, reason: str = 'not_interested', notes: str = None, user=None) -> dict:
        """
        Mark target as stopped with appropriate business trigger
        
        Args:
            reason: Stop reason - maps to State Machine triggers
            notes: Optional stop notes
            user: User marking as stopped
            
        Returns:
            dict: Update result from enhanced update_status()
        """
        # Map reasons to State Machine triggers
        trigger_mapping = {
            'not_interested': 'not_interested',
            'wrong_contact': 'wrong_contact',
            'invalid_contact_info': 'invalid_contact_info',
            'unsubscribed': 'unsubscribed',
            'manual_stop': 'manual_stop'
        }
        
        trigger = trigger_mapping.get(reason, 'manual_stop')
        stop_notes = f"Target stopped: {reason}"
        if notes:
            stop_notes += f" - {notes}"
        
        return self.update_status(
            new_status=self.Status.STOPPED,
            trigger=trigger,
            notes=stop_notes,
            user=user,
            source='business_result'
        )

    def request_callback(self, callback_date=None, notes: str = None, user=None) -> dict:
        """
        Mark target as callback pending with State Machine validation
        
        Args:
            callback_date: When callback was requested for
            notes: Optional callback notes
            user: User requesting callback
            
        Returns:
            dict: Update result from enhanced update_status()
        """
        callback_notes = "Callback requested"
        if callback_date:
            self.callback_date = callback_date
            callback_notes += f" for {callback_date}"
        if notes:
            callback_notes += f" - {notes}"
        
        return self.update_status(
            new_status=self.Status.CALLBACK_PENDING,
            trigger='callback_requested',
            notes=callback_notes,
            user=user,
            source='business_result'
        )

    def start_progress(self, notes: str = None, user=None) -> dict:
        """
        Mark target as in progress with State Machine validation
        
        Args:
            notes: Optional progress notes
            user: User starting progress
            
        Returns:
            dict: Update result from enhanced update_status()
        """
        # Determine appropriate trigger based on current status
        if self.status == self.Status.PENDING:
            trigger = 'campaign_started'
            progress_notes = "Campaign activities started"
        elif self.status == self.Status.CALLBACK_PENDING:
            trigger = 'callback_expired'
            progress_notes = "Callback period expired, resuming activities"
        else:
            trigger = 'first_activity_started'
            progress_notes = "Target activities in progress"
        
        if notes:
            progress_notes += f" - {notes}"
        
        return self.update_status(
            new_status=self.Status.IN_PROGRESS,
            trigger=trigger,
            notes=progress_notes,
            user=user,
            source='business_result'
        )

    def expire_callback(self, notes: str = None, user=None) -> dict:
        """
        Move from callback pending back to in progress when callback expires
        
        Args:
            notes: Optional expiration notes
            user: User processing expiration
            
        Returns:
            dict: Update result from enhanced update_status()
        """
        if self.status != self.Status.CALLBACK_PENDING:
            raise StandardizedValidationError(
                f"Cannot expire callback for target in status: {self.status}"
            )
        
        expiry_notes = "Callback period expired"
        if notes:
            expiry_notes += f" - {notes}"
        
        # Clear callback date when expired
        self.callback_date = None
        
        return self.update_status(
            new_status=self.Status.IN_PROGRESS,
            trigger='callback_expired',
            notes=expiry_notes,
            user=user,
            source='business_result'
        )
    
    def mark_as_active_due_to_campaign(self, campaign_status_trigger: str = 'campaign_activated', 
                                 notes: str = None, user=None) -> dict:
        """
        Marque le target comme actif suite à un changement de statut de campagne
        ✅ NOUVEAU : Utilise les triggers spécifiques aux campagnes
        
        Args:
            campaign_status_trigger: 'campaign_activated', 'campaign_resumed', etc.
            notes: Notes expliquant la raison
            user: Utilisateur déclenchant l'action
            
        Returns:
            dict: Résultat de la mise à jour de statut
        """

        print(f"Activating target due to campaign status change: {campaign_status_trigger}")
        # Mapping des triggers de campagne
        campaign_trigger_mapping = {
            'DRAFT_TO_ACTIVE': 'campaign_activated',
            'PAUSED_TO_ACTIVE': 'campaign_resumed', 
            'READY_TO_ACTIVE': 'campaign_activated',
            'GENERIC_ACTIVATION': 'campaign_reactivated'
        }
        
        # Utiliser le trigger fourni ou mapper selon le contexte
        trigger = campaign_trigger_mapping.get(campaign_status_trigger, campaign_status_trigger)
        
        activation_notes = f"Target activated due to campaign status change"
        if notes:
            activation_notes += f": {notes}"
        
        return self.update_status(
            new_status=self.Status.IN_PROGRESS,
            trigger=trigger,
            notes=activation_notes,
            user=user,
            source='business_result'
        )

    def handle_campaign_pause(self, notes: str = None, user=None) -> dict:
        """
        Gère la mise en pause du target suite à la mise en pause de la campagne
        ✅ NOUVEAU : Logique spécifique pour pause de campagne
        
        Args:
            notes: Notes expliquant la pause
            user: Utilisateur déclenchant l'action
            
        Returns:
            dict: Résultat de la mise à jour de statut
        """
        # Pour la pause, on peut soit :
        # 1. Laisser les targets en IN_PROGRESS (ils restent actifs conceptuellement)
        # 2. Les passer en PENDING temporairement
        # 3. Créer un nouveau statut PAUSED dans TargetStateMachine
        
        # Option 2 : Utiliser CALLBACK_PENDING comme état de pause temporaire
        if self.status == self.Status.IN_PROGRESS:
            pause_notes = f"Target paused due to campaign pause"
            if notes:
                pause_notes += f": {notes}"
                
            return self.update_status(
                new_status=self.Status.PENDING,
                trigger='campaign_paused',
                notes=pause_notes,
                user=user,
                source='business_result'
            )
        else:
            # Si target pas IN_PROGRESS, ne rien faire
            return {
                'status_updated': False,
                'reason': 'Target not in IN_PROGRESS state',
                'current_status': self.status
            }
    
    def get_available_actions(self) -> dict:
        """
        Get available actions based on current status using State Machine
        Useful for UI and API to show what actions are permitted
        
        Returns:
            dict: Available actions with their triggers and descriptions
        """
        current_status = self.status
        allowed_transitions = TargetStateMachine.get_allowed_transitions(current_status)
        
        actions = {}
        
        # Define action mappings
        action_mappings = {
            'IN_PROGRESS': {
                'start_progress': 'Begin working on this target',
                'continue_activities': 'Continue campaign activities'
            },
            'CALLBACK_PENDING': {
                'request_callback': 'Schedule callback with contact',
                'set_callback_date': 'Set or update callback date'
            },
            'COMPLETED': {
                'mark_completed_success': 'Mark as successfully completed',
                'mark_completed_meeting': 'Mark completed with meeting scheduled',
                'mark_completed_lead': 'Mark completed with lead created',
                'mark_completed_opportunity': 'Mark completed with opportunity created'
            },
            'STOPPED': {
                'mark_stopped_not_interested': 'Mark as not interested',
                'mark_stopped_wrong_contact': 'Mark as wrong contact',
                'mark_stopped_invalid_info': 'Mark as invalid contact info',
                'mark_stopped_unsubscribed': 'Mark as unsubscribed'
            }
        }
        
        # Build available actions based on allowed transitions
        for allowed_status in allowed_transitions:
            if allowed_status in action_mappings:
                actions.update(action_mappings[allowed_status])
        
        # Add universal actions for non-final states
        if not TargetStateMachine.is_final_state(current_status):
            actions['manual_status_change'] = 'Manually change status'
            actions['add_notes'] = 'Add notes without changing status'
        
        return {
            'current_status': current_status,
            'current_status_display': self.get_status_display(),
            'is_final_state': TargetStateMachine.is_final_state(current_status),
            'allowed_transitions': allowed_transitions,
            'available_actions': actions
        }

    def can_perform_action(self, action_type: str) -> bool:
        """
        Check if a specific action can be performed on this target
        
        Args:
            action_type: Type of action ('complete', 'stop', 'callback', 'progress')
            
        Returns:
            bool: True if action is allowed
        """
        current_status = self.status
        
        action_requirements = {
            'complete': ['IN_PROGRESS', 'CALLBACK_PENDING'],
            'stop': ['IN_PROGRESS', 'CALLBACK_PENDING'],
            'callback': ['IN_PROGRESS'],
            'progress': ['PENDING', 'CALLBACK_PENDING'],
            'expire_callback': ['CALLBACK_PENDING']
        }
        
        required_statuses = action_requirements.get(action_type, [])
        return current_status in required_statuses

    def get_status_history_summary(self) -> dict:
        """
        Get a summary of status changes from notes
        Useful for debugging and audit purposes
        
        Returns:
            dict: Summary of status transitions found in notes
        """
        if not self.notes:
            return {'transitions': [], 'total_changes': 0}
        
        import re
        
        # Pattern to match status transition notes
        transition_pattern = r'\[([\d\-: ]+)\] Status: (\w+) → (\w+)'
        
        transitions = []
        for match in re.finditer(transition_pattern, self.notes):
            timestamp_str, from_status, to_status = match.groups()
            transitions.append({
                'timestamp': timestamp_str,
                'from_status': from_status,
                'to_status': to_status
            })
        
        return {
            'transitions': transitions,
            'total_changes': len(transitions),
            'current_status': self.status
        }
    
    def get_state_machine_integration_status(self) -> dict:
        """
        Verify State Machine integration is working properly
        Useful for debugging and system health checks
        
        Returns:
            dict: Integration status report
        """
        try:
            # Test State Machine validation
            current_status = self.status
            allowed_transitions = TargetStateMachine.get_allowed_transitions(current_status)
            is_final_state = TargetStateMachine.is_final_state(current_status)
            
            # Test business trigger methods availability
            available_methods = []
            if self.can_perform_action('complete'):
                available_methods.append('mark_as_completed')
            if self.can_perform_action('stop'):
                available_methods.append('mark_as_stopped')
            if self.can_perform_action('callback'):
                available_methods.append('request_callback')
            if self.can_perform_action('progress'):
                available_methods.append('start_progress')
            
            # Check status consistency
            consistency_report = self.validate_status_consistency()
            
            # Check if notes contain State Machine transitions
            history_summary = self.get_status_history_summary()
            has_state_machine_transitions = any(
                'business result' in transition.get('notes', '') or 
                'trigger:' in transition.get('notes', '')
                for transition in history_summary.get('transitions', [])
            )
            
            return {
                'target_id': self.id,
                'campaign_id': self.campaign.id,
                'integration_status': 'active',
                'current_status': current_status,
                'is_final_state': is_final_state,
                'allowed_transitions': allowed_transitions,
                'available_business_methods': available_methods,
                'status_consistency': {
                    'is_consistent': consistency_report.get('is_consistent'),
                    'state_machine_compliant': consistency_report.get('state_machine_compliant', True)
                },
                'transition_history': {
                    'total_transitions': history_summary.get('total_changes', 0),
                    'has_state_machine_transitions': has_state_machine_transitions
                },
                'verification_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'target_id': self.id,
                'integration_status': 'error',
                'error': str(e),
                'verification_timestamp': timezone.now().isoformat()
            }