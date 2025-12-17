# backend/apps/opportunities/models/substage_metadata.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp


class SubStageMetadata(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Métadonnées détaillées pour les sous-étapes du pipeline.
    Contient les informations sur les stakeholders, départements, objectifs, etc.
    """
    
    # Relation OneToOne vers PipelineSubStage
    substage = models.OneToOneField(
        'PipelineSubStage',
        on_delete=models.CASCADE,
        related_name='metadata',
        verbose_name=_('Pipeline SubStage'),
        help_text=_('SubStage this metadata belongs to')
    )
    
    # Relations ManyToMany vers Contact (stakeholders)
    stakeholders = models.ManyToManyField(
        'accounts.Contact',
        related_name='substage_metadata',
        blank=True,
        verbose_name=_('Stakeholders'),
        help_text=_('Contacts involved in this substage')
    )
    
    # Département responsable
    department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Department'),
        help_text=_('Department responsible for this substage')
    )
    
    # Objectif de la sous-étape
    objective = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Objective'),
        help_text=_('Main objective of this substage')
    )
    
    # Critères de validation/décision
    validation_criteria = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Validation Criteria'),
        help_text=_('List of criteria to validate this substage')
    )
    
    # Critères de décision
    decision_criteria = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Decision Criteria'),
        help_text=_('List of decision criteria for this substage')
    )
    
    # Notes sur les processus
    process_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Process Notes'),
        help_text=_('Notes about the process for this substage')
    )
    
    # Ressources nécessaires
    required_resources = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Required Resources'),
        help_text=_('List of resources needed for this substage')
    )
    
    # Risques identifiés
    identified_risks = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Identified Risks'),
        help_text=_('List of risks identified for this substage')
    )
    
    # Actions de mitigation
    mitigation_actions = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Mitigation Actions'),
        help_text=_('List of actions to mitigate risks')
    )
    
    # Informations sur les approbations
    approval_info = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Approval Information'),
        help_text=_('Information about approvals needed')
    )
    
    # Métriques de succès
    success_metrics = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Success Metrics'),
        help_text=_('List of metrics to measure success')
    )
    
    # Outils et documents
    tools_and_documents = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Tools and Documents'),
        help_text=_('List of tools and documents needed')
    )
    
    # Budget estimé
    estimated_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Estimated Budget'),
        help_text=_('Estimated budget for this substage')
    )
    
    # Coût réel
    actual_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Actual Cost'),
        help_text=_('Actual cost incurred for this substage')
    )
    
    # Priorité
    priority = models.CharField(
        max_length=20,
        choices=[
            ('LOW', _('Low')),
            ('MEDIUM', _('Medium')),
            ('HIGH', _('High')),
            ('CRITICAL', _('Critical')),
        ],
        default='MEDIUM',
        verbose_name=_('Priority'),
        help_text=_('Priority level of this substage')
    )
    
    # Tags personnalisés
    custom_tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Custom Tags'),
        help_text=_('Custom tags for categorization')
    )
    
    # Données historiques
    historical_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Historical Data'),
        help_text=_('Historical data and performance metrics')
    )
    
    # Commentaires internes
    internal_comments = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Internal Comments'),
        help_text=_('Internal comments for the team')
    )
    
    # Dernière révision
    last_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Reviewed At'),
        help_text=_('When this metadata was last reviewed')
    )
    
    # Révisé par
    last_reviewed_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='reviewed_substage_metadata',
        null=True,
        blank=True,
        verbose_name=_('Last Reviewed By'),
        help_text=_('User who last reviewed this metadata')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['substage', 'department', 'priority']
    )):
        db_table = 'substage_metadata'
        verbose_name = _('SubStage Metadata')
        verbose_name_plural = _('SubStage Metadata')
        ordering = ['substage__order']

    def __str__(self):
        return f"Metadata - {self.substage}"

    def get_department_display(self):
        """
        Récupère le nom d'affichage du département
        """
        if self.department:
            return self.department.get_name_display()
        return None

    # def set_department_by_name(self, department_name):
    #     """
    #     Définit le département par nom
    #     """
    #     try:
    #         department = StandardDepartment.objects.get(name=department_name)
    #         self.department = department
    #         self.save(update_fields=['department'])
    #     except StandardDepartment.DoesNotExist:
    #         from core.exceptions import StandardizedValidationError
    #         raise StandardizedValidationError(f"Department '{department_name}' not found")

    def add_stakeholder(self, contact):
        """
        Ajoute un stakeholder à cette sous-étape
        """
        if contact.client_id == self.client_id:
            self.stakeholders.add(contact)
        else:
            from core.exceptions import StandardizedValidationError
            from core.error_messages import CoreErrorMessages
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)

    def remove_stakeholder(self, contact):
        """
        Retire un stakeholder de cette sous-étape
        """
        self.stakeholders.remove(contact)

    def get_stakeholders_by_influence(self, influence_level):
        """
        Récupère les stakeholders par niveau d'influence
        """
        return self.stakeholders.filter(influence_level=influence_level)

    def get_decision_makers(self):
        """
        Récupère les décideurs
        """
        return self.get_stakeholders_by_influence('DECISION_MAKER')

    def get_influencers(self):
        """
        Récupère les influenceurs
        """
        return self.get_stakeholders_by_influence('INFLUENCER')

    def get_champions(self):
        """
        Récupère les champions
        """
        return self.get_stakeholders_by_influence('CHAMPION')

    def add_validation_criterion(self, criterion):
        """
        Ajoute un critère de validation
        """
        if criterion not in self.validation_criteria:
            self.validation_criteria.append(criterion)
            self.save(update_fields=['validation_criteria'])

    def remove_validation_criterion(self, criterion):
        """
        Retire un critère de validation
        """
        if criterion in self.validation_criteria:
            self.validation_criteria.remove(criterion)
            self.save(update_fields=['validation_criteria'])

    def add_decision_criterion(self, criterion):
        """
        Ajoute un critère de décision
        """
        if criterion not in self.decision_criteria:
            self.decision_criteria.append(criterion)
            self.save(update_fields=['decision_criteria'])

    def remove_decision_criterion(self, criterion):
        """
        Retire un critère de décision
        """
        if criterion in self.decision_criteria:
            self.decision_criteria.remove(criterion)
            self.save(update_fields=['decision_criteria'])

    def add_risk(self, risk_description, probability='MEDIUM', impact='MEDIUM'):
        """
        Ajoute un risque identifié
        """
        from django.utils import timezone
        risk = {
            'description': risk_description,
            'probability': probability,
            'impact': impact,
            'identified_at': timezone.now().isoformat()
        }
        self.identified_risks.append(risk)
        self.save(update_fields=['identified_risks'])

    def add_mitigation_action(self, action_description, responsible=None, due_date=None):
        """
        Ajoute une action de mitigation
        """
        from django.utils import timezone
        action = {
            'description': action_description,
            'responsible': responsible,
            'due_date': due_date.isoformat() if due_date else None,
            'created_at': timezone.now().isoformat(),
            'status': 'PENDING'
        }
        self.mitigation_actions.append(action)
        self.save(update_fields=['mitigation_actions'])

    def add_custom_tag(self, tag):
        """
        Ajoute un tag personnalisé
        """
        if tag not in self.custom_tags:
            self.custom_tags.append(tag)
            self.save(update_fields=['custom_tags'])

    def remove_custom_tag(self, tag):
        """
        Retire un tag personnalisé
        """
        if tag in self.custom_tags:
            self.custom_tags.remove(tag)
            self.save(update_fields=['custom_tags'])

    def set_approval_info(self, approver, approval_type, required_by=None):
        """
        Définit les informations d'approbation
        """
        self.approval_info = {
            'approver': approver,
            'approval_type': approval_type,
            'required_by': required_by.isoformat() if required_by else None,
            'status': 'PENDING'
        }
        self.save(update_fields=['approval_info'])

    def mark_as_reviewed(self, user):
        """
        Marque les métadonnées comme révisées
        """
        from django.utils import timezone
        self.last_reviewed_at = timezone.now()
        self.last_reviewed_by = user
        self.save(update_fields=['last_reviewed_at', 'last_reviewed_by'])

    def get_budget_variance(self):
        """
        Calcule la variance budgétaire
        """
        if not self.estimated_budget or not self.actual_cost:
            return None
        
        return self.actual_cost - self.estimated_budget

    def get_budget_variance_percentage(self):
        """
        Calcule la variance budgétaire en pourcentage
        """
        if not self.estimated_budget or not self.actual_cost:
            return None
        
        if self.estimated_budget == 0:
            return None
        
        return round(((self.actual_cost - self.estimated_budget) / self.estimated_budget) * 100, 2)

    @property
    def is_high_priority(self):
        """
        Vérifie si c'est une priorité haute
        """
        return self.priority in ['HIGH', 'CRITICAL']

    @property
    def has_pending_approvals(self):
        """
        Vérifie s'il y a des approbations en attente
        """
        return self.approval_info.get('status') == 'PENDING'

    @property
    def risk_count(self):
        """
        Nombre de risques identifiés
        """
        return len(self.identified_risks)

    @property
    def stakeholder_count(self):
        """
        Nombre de stakeholders
        """
        return self.stakeholders.count()

    @classmethod
    def create_for_substage(cls, substage, user=None):
        """
        Crée des métadonnées pour une sous-étape
        """
        return cls.objects.create(
            substage=substage,
            client_id=substage.client_id,
            user=user
        )