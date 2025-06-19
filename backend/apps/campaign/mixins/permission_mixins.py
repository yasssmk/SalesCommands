# apps/campaign/mixins/permission_mixins.py

from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages, CoreErrorMessages
from core.client_scope import ClientScopeManager
from apps.campaign.config.variables import (
    CAMPAIGN_FORBIDDEN_STATES,
    FIELD_NAMES,
    CAMPAIGN_PERMISSIONS
)


class CampaignPermissionMixin(ClientScopeManager.ViewMixin):
    """
    Mixin pour centraliser les validations de permissions récurrentes des campagnes.
    Version MVP - Focus sur les validations les plus courantes.
    
    Hérite de ClientScopeManager.ViewMixin pour avoir accès aux méthodes de validation client_id.
    """
    
    def validate_campaign_ownership(self, campaign, allow_stakeholders=False):
        """
        Valider que l'utilisateur peut accéder/modifier la campagne
        
        Args:
            campaign: Instance de Campaign
            allow_stakeholders: Si True, autorise les stakeholders avec permissions
        """
        user = self.request.user
        
        # Vérifier si c'est le propriétaire
        if campaign.owner == user:
            return True
            
        # Si stakeholders autorisés, vérifier les permissions
        if allow_stakeholders:

            if user.has_perm(CAMPAIGN_PERMISSIONS['CHANGE']):
                return True
                
            # Vérifier si l'utilisateur est stakeholder de cette campagne
            from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
            is_stakeholder = CampaignStakeholder.objects.filter(
                campaign=campaign,
                user=user
            ).exists()
            
            if is_stakeholder:
                return True
        
        raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
    
    def validate_campaign_state(self, campaign, forbidden_states=None):
        """
        Valider que la campagne n'est pas dans un état interdit
        
        Args:
            campaign: Instance de Campaign
            forbidden_states: Liste des états interdits (défaut: COMPLETED, CANCELLED)
        """

        if forbidden_states is None:
            forbidden_states = CAMPAIGN_FORBIDDEN_STATES
            
        if campaign.status in forbidden_states:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=campaign.status)
            )
    
    def get_validated_campaign(self, pk=None, require_ownership=True, allow_stakeholders=False, 
                             check_state=True):
        """
        Helper pour récupérer et valider une campagne en une opération
        
        Args:
            pk: ID de la campagne (si None, utilise self.get_object())
            require_ownership: Si True, vérifie la propriété/stakeholder
            allow_stakeholders: Si True, autorise les stakeholders
            check_state: Si True, vérifie que la campagne n'est pas terminée
            
        Returns:
            Instance de Campaign validée
        """
        try:
            if pk:
                from apps.campaign.models.campaign import Campaign
                campaign = Campaign.objects.get(pk=pk, client_id=self.get_client_id())
            else:
                campaign = self.get_object()
                
        except Campaign.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        # Validation client scope
        self.validate_client_id(campaign)
        
        # Validation ownership si requis
        if require_ownership:
            self.validate_campaign_ownership(campaign, allow_stakeholders=allow_stakeholders)
        
        # Validation état si requis
        if check_state:
            self.validate_campaign_state(campaign)
        
        return campaign
    
    def validate_campaign_related_object(self, obj, allow_stakeholders=False):
        """
        Valider un objet lié à une campagne (objective, target, stakeholder)
        
        Args:
            obj: Objet avec une relation FK vers Campaign
            allow_stakeholders: Si True, autorise les stakeholders
        """
        # Validation client scope
        self.validate_client_id(obj)
        
        # Récupérer la campagne liée
        campaign = obj.campaign
        
        # Validation ownership
        self.validate_campaign_ownership(campaign, allow_stakeholders=allow_stakeholders)
        
        return campaign
    
    def get_validated_campaign_from_data(self, data_key=None, allow_stakeholders=False):
        """
        Valider une campagne depuis les données de la requête
        
        Args:
            data_key: Clé dans les données contenant l'ID de campagne
            allow_stakeholders: Si True, autorise les stakeholders
            
        Returns:
            Instance de Campaign validée
        """

        if data_key is None:
            data_key = FIELD_NAMES['CAMPAIGN']
            
        # Extraire campaign depuis les données validées du serializer
        campaign = None
        
        # Essayer d'abord depuis les données validées du serializer
        if hasattr(self, 'get_serializer'):
            serializer = self.get_serializer(data=self.request.data)
            if serializer.is_valid():
                campaign = serializer.validated_data.get(data_key)
        
        # Fallback: essayer depuis les données brutes
        if not campaign:
            # ✅ Utilisation des constantes pour les noms de champs
            campaign_id = (
                self.request.data.get(data_key) or 
                self.request.data.get(FIELD_NAMES['CAMPAIGN_ID'])
            )
            if campaign_id:
                try:
                    from apps.campaign.models.campaign import Campaign
                    campaign = Campaign.objects.get(pk=campaign_id, client_id=self.get_client_id())
                except Campaign.DoesNotExist:
                    raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        if not campaign:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Campaign")
            )
        
        # Validation ownership
        self.validate_campaign_ownership(campaign, allow_stakeholders=allow_stakeholders)
        
        return campaign
    
    def _get_validated_account(self, account_id):
        """
        Helper pour récupérer et valider un account avec client scope
        
        Args:
            account_id: ID de l'account
            
        Returns:
            Instance d'Account validée
        """
        try:
            from apps.accounts.models import Account
            account = Account.objects.get(id=account_id, client_id=self.get_client_id())
            return account
        except Account.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

    def _get_validated_contact(self, contact_id):
        """
        Helper pour récupérer et valider un contact avec client scope
        
        Args:
            contact_id: ID du contact
            
        Returns:
            Instance de Contact validée
        """
        try:
            from apps.accounts.models import Contact
            contact = Contact.objects.get(id=contact_id, account__client_id=self.get_client_id())
            return contact
        except Contact.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)