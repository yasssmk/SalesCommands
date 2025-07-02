# apps/activities/serializers/activity_serializer.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.activities.models import Activity, ActivityCampaign, ActivitySequence
from apps.accounts.models import Account, Contact
from apps.campaign.models import Campaign, CampaignTarget


class ActivitySequenceSerializer(serializers.ModelSerializer):
    """Serializer for ActivitySequence model"""
    sequence_outcome_display = serializers.SerializerMethodField(read_only=True)
    source_type_display = serializers.SerializerMethodField(read_only=True)
    can_attempt_call = serializers.SerializerMethodField(read_only=True)

    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    sequence_variant_display = serializers.SerializerMethodField(read_only=True)
    is_from_sequence = serializers.SerializerMethodField(read_only=True)
    full_sequence_info = serializers.SerializerMethodField(read_only=True)


    
    class Meta:
        model = ActivitySequence
        fields = [
            'id', 'source_type', 'source_type_display', 'sequence_position',
            'sequence_outcome', 'sequence_outcome_display', 'call_attempts',
            'can_attempt_call', 'callback_requested_date', 'sequence_paused_until',
            'days_since_last_sequence_activity', 'next_sequence_activity',
            'sequence_type', 'sequence_type_display',
            'sequence_variant', 'sequence_variant_display',
            'is_from_sequence', 'full_sequence_info',
        ]
        read_only_fields = ['id', 'days_since_last_sequence_activity']
    
    def get_sequence_outcome_display(self, obj):
        """Get the display name for sequence outcome"""
        if obj.sequence_outcome:
            return obj.get_sequence_outcome_display()
        return None
    
    def get_source_type_display(self, obj):
        """Get the display name for source type"""
        return obj.get_source_type_display()
    
    def get_can_attempt_call(self, obj):
        """Check if another call attempt is allowed"""
        return obj.call_attempts < 3
    
    def get_sequence_type_display(self, obj):
        """Get human-readable display for sequence type"""
        return obj.get_sequence_type_display()
    
    def get_sequence_variant_display(self, obj):
        """Get human-readable display for sequence variant"""
        return obj.get_sequence_variant_display()
    
    def get_is_from_sequence(self, obj):
        """Check if this activity is from a sequence"""
        return obj.is_from_sequence()
    
    def get_full_sequence_info(self, obj):
        """Get complete sequence information for API responses"""
        return obj.get_full_sequence_info()
    



class ActivityCampaignSerializer(serializers.ModelSerializer):
    """Serializer for ActivityCampaign model"""
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    
    class Meta:
        model = ActivityCampaign
        fields = [
            'id', 'campaign', 'campaign_name', 'campaign_target',
            'meeting_scheduled', 'opportunity_created'
        ]
        read_only_fields = ['id']


class ActivitySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Main serializer for Activity model with optional nested campaign and sequence info
    """
    # Nested serializers for related models
    campaign_info = ActivityCampaignSerializer(read_only=True)
    sequence_info = ActivitySequenceSerializer(read_only=True)

    # Display fields
    activity_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    
    # Related object displays
    account_name = serializers.CharField(source='account.company_name', read_only=True)
    owner_id = serializers.UUIDField(source='owner.id', read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True) 
    owner_name = serializers.SerializerMethodField(read_only=True)
    contact_names = serializers.SerializerMethodField(read_only=True)
    
    # Write fields for creating activities
    contact_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of contact IDs to associate with this activity"
    )

    contact_validation_info = serializers.SerializerMethodField(read_only=True)

    result = serializers.SerializerMethodField(read_only=True)
    notes = serializers.SerializerMethodField(read_only=True)

    previous_activity_info = serializers.SerializerMethodField(read_only=True)
    next_activity_info = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Activity
        fields = [
            'id', 'title', 'activity_type', 'activity_type_display',
            'description', 'account', 'account_name', 'contacts', 'contact_ids',
            'contact_names', 'owner_id', 'owner_email', 'owner_name',
            'scheduled_end', 'status', 'status_display',  'result', 'notes', 'previous_activity_info', 'next_activity_info',
            'contact_validation_info','completed_at','outcome_notes', 'opportunity', 'campaign_info', 'sequence_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    
    def get_activity_type_display(self, obj):
        """Get the display name for activity type"""
        return obj.get_activity_type_display()
    
    def get_status_display(self, obj):
        """Get the display name for status"""
        return obj.get_status_display()
    
    def get_contact_names(self, obj):
        """Get names of associated contacts"""
        return [f"{c.first_name} {c.last_name}" for c in obj.contacts.all()]
    
    def get_owner_name(self, obj):
        """Get owner full name using get_full_name() method"""
        if not obj.owner:
            return None
        
        try:
            # Utiliser get_full_name() qui gère first_name + last_name avec fallback
            full_name = obj.owner.get_full_name()
            
            # Si get_full_name() retourne juste l'email/username, essayer de construire un nom
            if full_name == obj.owner.email:
                # Fallback : construire à partir de first_name et last_name
                if obj.owner.first_name or obj.owner.last_name:
                    name_parts = []
                    if obj.owner.first_name:
                        name_parts.append(obj.owner.first_name)
                    if obj.owner.last_name:
                        name_parts.append(obj.owner.last_name)
                    return ' '.join(name_parts) if name_parts else obj.owner.email
                else:
                    return obj.owner.email
            
            return full_name
            
        except AttributeError:
            # Fallback si get_full_name() n'existe pas
            if hasattr(obj.owner, 'first_name') and hasattr(obj.owner, 'last_name'):
                name_parts = []
                if obj.owner.first_name:
                    name_parts.append(obj.owner.first_name)
                if obj.owner.last_name:
                    name_parts.append(obj.owner.last_name)
                return ' '.join(name_parts) if name_parts else str(obj.owner)
            
            return str(obj.owner)
    
    def get_contact_validation_info(self, obj):
        """Get validation info for contacts in this activity"""
        if not obj.contacts.exists():
            return None
        
        contact = obj.contacts.first()
        return {
            'email_is_valid': contact.email_is_valid,
            'phone_is_valid': contact.phone_is_valid,
            'opted_out': contact.opted_out,
            'has_email': bool(contact.email),
            'has_phone': bool(contact.phone_number),
            'has_linkedin': bool(contact.linkedin),
        }
    
    def validate(self, data):
        """Validate the activity data"""
        try:
            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            
            # Validate account belongs to client
            if 'account' in data:
                account = data['account']
                self.validate_client_id(account)
            
            # Validate scheduled dates
            if 'scheduled_end' in data and 'scheduled_start' in data:
                if data['scheduled_end'] < data['scheduled_start']:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATE_RANGE.format(
                            start_date=data['scheduled_start'],
                            end_date=data['scheduled_end']
                        )
                    )
            
            return super().validate(data)
            
        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)
    
    def create(self, validated_data):
        """Create activity with optional contacts"""
        contact_ids = validated_data.pop('contact_ids', [])
        
        # Set owner to current user if not provided
        if 'owner' not in validated_data and self.context.get('request'):
            validated_data['owner'] = self.context['request'].user
        
        activity = super().create(validated_data)
        
        # Add contacts if provided
        if contact_ids:
            contacts = Contact.objects.filter(
                id__in=contact_ids,
                account=activity.account,
                client_id=self.get_client_id()
            )
            activity.contacts.set(contacts)
        
        return activity
    
    def get_result(self, obj):
        """
        Get activity result - obligatoire si completed
        ✅ AMÉLIORÉ : Logique d'extraction plus robuste et contextuelle
        """
        if obj.status != Activity.Status.COMPLETED:
            return None
        
        # 1. Vérifier d'abord si on a sequence_outcome (plus fiable)
        if hasattr(obj, 'sequence_info') and obj.sequence_info and obj.sequence_info.sequence_outcome:
            sequence_outcome = obj.sequence_info.sequence_outcome
            
            # Mapper les sequence_outcome vers des résultats standardisés
            outcome_mapping = {
                'SUCCESSFUL': 'SUCCESSFUL',
                'NO_ANSWER': 'NO_ANSWER', 
                'BOUNCED': 'BOUNCED',
                'NOT_INTERESTED': 'NOT_INTERESTED',
                'CALLBACK_REQUESTED': 'CALLBACK_REQUESTED',
                'INVALID_CONTACT': 'INVALID_PHONE_NUMBER',
                'MEETING_SCHEDULED': 'MEETING_SCHEDULED',
                'OPPORTUNITY_CREATED': 'OPPORTUNITY_CREATED'
            }
            
            if sequence_outcome in outcome_mapping:
                return outcome_mapping[sequence_outcome]
        
        # 2. Fallback : extraction depuis outcome_notes avec logique améliorée
        outcome_notes = (obj.outcome_notes or "").lower().strip()
        
        if not outcome_notes:
            return "COMPLETED"  # Activité complétée sans détails
        
        # 3. Patterns de détection par ordre de priorité
        result_patterns = [
            # Résultats spécifiques en premier
            (['meeting scheduled', 'meeting booked', 'rdv programmé'], 'MEETING_SCHEDULED'),
            (['opportunity created', 'opportunité créée', 'deal created'], 'OPPORTUNITY_CREATED'),
            (['callback requested', 'call back', 'rappel demandé'], 'CALLBACK_REQUESTED'),
            (['not interested', 'pas intéressé', 'not qualified'], 'NOT_INTERESTED'),
            (['bounced', 'bounce', 'email bounce'], 'BOUNCED'),
            (['no answer', 'pas de réponse', 'voicemail'], 'NO_ANSWER'),
            (['invalid phone', 'numéro invalide', 'wrong number'], 'INVALID_PHONE_NUMBER'),
            (['successful', 'succès', 'contact established'], 'SUCCESSFUL'),
        ]
        
        # 4. Recherche de patterns
        for patterns, result_code in result_patterns:
            if any(pattern in outcome_notes for pattern in patterns):
                return result_code
        
        # 5. Fallback par type d'activité
        activity_type_defaults = {
            'EMAIL': 'EMAIL_SENT',
            'CALL': 'CALL_ATTEMPTED', 
            'LINKEDIN': 'LINKEDIN_MESSAGE_SENT',
            'MEETING': 'MEETING_COMPLETED',
            'TASK': 'TASK_COMPLETED'
        }
        
        return activity_type_defaults.get(obj.activity_type, 'COMPLETED')
    
    
    def get_notes(self, obj):
        """
        Get activity notes - présent si completed, avec informations contextuelles
        ✅ AMÉLIORÉ : Inclut informations supplémentaires si disponibles
        """
        if obj.status != Activity.Status.COMPLETED:
            return None
        
        # Notes de base
        base_notes = obj.outcome_notes or ""
        
        # ✅ AJOUT : Enrichir avec des informations contextuelles
        additional_info = []
        
        # Ajouter info de séquence si disponible
        if hasattr(obj, 'sequence_info') and obj.sequence_info:
            seq_info = obj.sequence_info
            if seq_info.sequence_position:
                additional_info.append(f"Sequence step {seq_info.sequence_position}")
            
            if seq_info.call_attempts and seq_info.call_attempts > 1:
                additional_info.append(f"Call attempt #{seq_info.call_attempts}")
        
        # Ajouter info de callback si disponible  
        if (hasattr(obj, 'sequence_info') and obj.sequence_info and 
            obj.sequence_info.callback_requested_date):
            callback_date = obj.sequence_info.callback_requested_date
            additional_info.append(f"Callback requested for {callback_date}")
        
        # Combiner notes et informations supplémentaires
        if additional_info:
            context_info = " | ".join(additional_info)
            if base_notes:
                return f"{base_notes} [{context_info}]"
            else:
                return f"[{context_info}]"
        
        return base_notes
    
    def get_previous_activity_info(self, obj):
        """
        Get previous activity summary
        ✅ OPTIMISÉ : Utilise relations préchargées et logique unifiée
        """
        if not hasattr(obj, 'previous_activity') or not obj.previous_activity:
            return None
        
        try:
            prev = obj.previous_activity
            
            # Utiliser la logique unifiée de get_result pour cohérence
            result = None
            if prev.status == Activity.Status.COMPLETED:
                # Créer un contexte temporaire pour réutiliser get_result()
                temp_serializer = self.__class__()
                result = temp_serializer.get_result(prev)
            
            return {
                'id': prev.id,
                'activity_type': prev.activity_type,
                'activity_type_display': prev.get_activity_type_display(),
                'status': prev.status,
                'status_display': prev.get_status_display(),
                'result': result,
                'completed_at': prev.completed_at.isoformat() if prev.completed_at else None,
                'sequence_position': getattr(prev.sequence_info, 'sequence_position', None) if hasattr(prev, 'sequence_info') and prev.sequence_info else None
            }
            
        except Exception as e:
            # Fallback silencieux si relations mal préchargées
            return {
                'id': getattr(obj.previous_activity, 'id', None),
                'error': 'Relation not properly loaded'
            }

    def get_next_activity_info(self, obj):
        """
        Get next activity summary  
        ✅ OPTIMISÉ : Utilise relations préchargées et logique unifiée
        """
        if not hasattr(obj, 'next_activity') or not obj.next_activity:
            return None
        
        try:
            next_act = obj.next_activity
            
            # Utiliser la logique unifiée de get_result pour cohérence
            result = None
            if next_act.status == Activity.Status.COMPLETED:
                # Créer un contexte temporaire pour réutiliser get_result()
                temp_serializer = self.__class__()
                result = temp_serializer.get_result(next_act)
            
            return {
                'id': next_act.id,
                'activity_type': next_act.activity_type,
                'activity_type_display': next_act.get_activity_type_display(),
                'status': next_act.status,
                'status_display': next_act.get_status_display(), 
                'result': result,
                'scheduled_start': next_act.scheduled_start.isoformat() if next_act.scheduled_start else None,
                'sequence_position': getattr(next_act.sequence_info, 'sequence_position', None) if hasattr(next_act, 'sequence_info') and next_act.sequence_info else None
            }
            
        except Exception as e:
            # Fallback silencieux si relations mal préchargées
            return {
                'id': getattr(obj.next_activity, 'id', None),
                'error': 'Relation not properly loaded'
            }
    

class ActivityWithCampaignSerializer(ActivitySerializer):
    """
    Serializer for creating activities with campaign information
    """
    # Campaign-specific fields
    campaign_id = serializers.IntegerField(write_only=True)
    campaign_target_id = serializers.IntegerField(write_only=True)
    
    # Sequence-specific fields
    sequence_position = serializers.IntegerField(write_only=True, required=False)
    source_type = serializers.CharField(
        write_only=True,
        default=ActivitySequence.SourceType.CAMPAIGN
    )
    
    class Meta(ActivitySerializer.Meta):
        fields = ActivitySerializer.Meta.fields + [
            'campaign_id', 'campaign_target_id', 'sequence_position', 'source_type'
        ]
    
    def validate(self, data):
        """Validate campaign-specific data"""
        data = super().validate(data)
        
        # Validate campaign exists and belongs to user
        if 'campaign_id' in data:
            try:
                campaign = Campaign.objects.get(
                    id=data['campaign_id'],
                    client_id=self.get_client_id()
                )
                
                # Check if user owns the campaign
                if self.context.get('request') and hasattr(self.context['request'], 'user'):
                    if campaign.owner != self.context['request'].user:
                        raise StandardizedValidationError(
                            "You can only create activities for your own campaigns"
                        )
                
            except Campaign.DoesNotExist:
                raise StandardizedValidationError("Campaign not found")
        
        # Validate campaign target
        if 'campaign_target_id' in data:
            try:
                campaign_target = CampaignTarget.objects.get(
                    id=data['campaign_target_id'],
                    campaign_id=data.get('campaign_id'),
                    client_id=self.get_client_id()
                )
                
                # Ensure activity account matches campaign target account
                if 'account' in data and data['account'] != campaign_target.account:
                    raise StandardizedValidationError(
                        "Activity account must match campaign target account"
                    )
                
            except CampaignTarget.DoesNotExist:
                raise StandardizedValidationError("Campaign target not found")
        
        return data
    
    def create(self, validated_data):
        """Create activity with campaign and sequence information"""
        # Extract campaign-specific data
        campaign_id = validated_data.pop('campaign_id')
        campaign_target_id = validated_data.pop('campaign_target_id')
        sequence_position = validated_data.pop('sequence_position', None)
        source_type = validated_data.pop('source_type', ActivitySequence.SourceType.CAMPAIGN)
        
        # Create the activity
        activity = super().create(validated_data)
        
        # Create campaign information
        campaign = Campaign.objects.get(id=campaign_id)
        campaign_target = CampaignTarget.objects.get(id=campaign_target_id)
        
        ActivityCampaign.objects.create(
            activity=activity,
            campaign=campaign,
            campaign_target=campaign_target
        )
        
        # Create sequence information if provided
        if sequence_position is not None:
            ActivitySequence.objects.create(
                activity=activity,
                source_type=source_type,
                sequence_position=sequence_position
            )
        
        return activity


class ActivityCompletionSerializer(serializers.Serializer):
    """
    Serializer for completing activities with outcomes
    """
    outcome_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Notes about the outcome of the activity"
    )
    
    # Campaign-specific outcomes
    meeting_scheduled = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether a meeting was scheduled as a result"
    )
    
    opportunity_created = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether an opportunity was created as a result"
    )
    
    # Sequence-specific outcomes
    sequence_outcome = serializers.ChoiceField(
        choices=ActivitySequence.SequenceOutcome.choices,
        required=False,
        help_text="Outcome of the sequence activity"
    )
    
    callback_requested_date = serializers.DateField(
        required=False,
        help_text="Date when contact requested to be called back"
    )

    
    
    def validate(self, data):
        """Validate completion data"""
        # If sequence outcome is callback requested, require callback date
        if (data.get('sequence_outcome') == ActivitySequence.SequenceOutcome.CALLBACK_REQUESTED and
            not data.get('callback_requested_date')):
            raise serializers.ValidationError(
                "Callback date is required when outcome is 'callback requested'"
            )
        
        return data