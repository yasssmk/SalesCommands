# backend/apps/opportunities/models/pipeline_substage.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from ..config.pipeline_stages import PipelineStagesConfig
from .pipeline_stage import PipelineStage
from django.db import transaction
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages


class PipelineSubStage(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Sous-étapes du pipeline de vente.
    Chaque sous-étape appartient à une étape principale (PipelineStage).
    """
    
    # Import des constantes depuis la configuration
    SubStageType = PipelineStagesConfig.SubStageType
    SubStageStatus = PipelineStagesConfig.SubStageStatus
    
    # Relations
    stage = models.ForeignKey(
        'PipelineStage',
        on_delete=models.CASCADE,
        related_name='substages',
        verbose_name=_('Pipeline Stage'),
        help_text=_('Parent stage this substage belongs to')
    )
    
    # Relations pour la performance (linked list)
    previous_substage = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='next_substage_rel',
        null=True,
        blank=True,
        verbose_name=_('Previous SubStage'),
        help_text=_('Previous substage in the sequence')
    )
    
    next_substage = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='previous_substage_rel',
        null=True,
        blank=True,
        verbose_name=_('Next SubStage'),
        help_text=_('Next substage in the sequence')
    )
    
    # Informations de base
    name = models.CharField(
        max_length=200,
        verbose_name=_('SubStage Name'),
        help_text=_('Name of the pipeline substage')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Description of what happens in this substage')
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Order'),
        help_text=_('Order of this substage within the parent stage')
    )
    
    # Type de sous-étape
    substage_type = models.CharField(
        max_length=30,
        choices=SubStageType.choices,
        default=SubStageType.INTERACTION_CLIENT,
        verbose_name=_('SubStage Type'),
        help_text=_('Type of this substage')
    )

    stakeholders = models.ManyToManyField(
        'accounts.Contact',
        blank=True,
        related_name='pipeline_substages',
        verbose_name=_('Stakeholders'),
        help_text=_('Stakeholders directly involved in this substage')
    )
    
    # Statut
    status = models.CharField(
        max_length=20,
        choices=SubStageStatus.choices,
        default=SubStageStatus.NOT_STARTED,
        verbose_name=_('Status'),
        help_text=_('Current status of this substage')
    )
    
    # Durée et dates
    estimated_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Estimated Duration (days)'),
        help_text=_('Estimated duration in days for this substage')
    )
    
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
        help_text=_('Planned or actual start date')
    )
    
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('End Date'),
        help_text=_('Planned or actual end date')
    )
    
    actual_start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Actual Start Date'),
        help_text=_('When this substage actually started')
    )
    
    actual_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Actual End Date'),
        help_text=_('When this substage actually ended')
    )
    
    # Activation
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether this substage is active')
    )

    overdue = models.BooleanField(
        default=False,
        verbose_name=_('Is Overdue'),
        help_text=_('Whether this substage is overdue (automatically calculated)')
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about this substage')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['stage', 'order', 'status', 'substage_type', 'overdue']
    )):
        db_table = 'pipeline_substages'
        verbose_name = _('Pipeline SubStage')
        verbose_name_plural = _('Pipeline SubStages')
        ordering = ['stage', 'order', 'name']

    def save(self, *args, **kwargs):
        """
        ✅ CORRECTION FINALE : Sauvegarde simple pour MVP
        """
        # ✅ Validation de base
        self.clean()
        
        # ✅ Gestion basique des ordres sans conflits automatiques
        if not self.order:
            # Calculer l'ordre suivant seulement si pas spécifié
            from django.db.models import Max
            
            # Déterminer le contexte (template ou opportunité)
            filter_kwargs = {'client_id': self.client_id}
            if self.template_id:
                filter_kwargs['template_id'] = self.template_id
            elif hasattr(self, 'opportunity_pipeline_id') and self.opportunity_pipeline_id:
                filter_kwargs['opportunity_pipeline_id'] = self.opportunity_pipeline_id
            
            max_order = PipelineStage.objects.filter(**filter_kwargs).aggregate(
                Max('order')
            )['order__max'] or 0
            self.order = max_order + 1
        
        # ✅ Sauvegarde simple sans linked list automatique
        super().save(*args, **kwargs)

    def _handle_order_conflicts(self):
        """
        ✅ MVP : Désactivé - On gère les ordres manuellement
        """
        pass

    def _update_linked_list(self):
        """
        ✅ MVP : Désactivé - Trop complexe pour un MVP
        """
        pass

    def get_next_stage(self):
        """
        ✅ Récupération du stage suivant via requête simple
        """
        # Déterminer le contexte (template ou opportunité)
        filter_kwargs = {'client_id': self.client_id}
        if self.template:
            filter_kwargs['template'] = self.template
        elif self.opportunity_pipeline:
            filter_kwargs['opportunity_pipeline'] = self.opportunity_pipeline
        else:
            return None
        
        return PipelineStage.objects.filter(
            order__gt=self.order,
            is_active=True,
            **filter_kwargs
        ).order_by('order').first()

    def get_previous_stage(self):
        """
        ✅ Récupération du stage précédent via requête simple
        """
        # Déterminer le contexte (template ou opportunité)
        filter_kwargs = {'client_id': self.client_id}
        if self.template:
            filter_kwargs['template'] = self.template
        elif self.opportunity_pipeline:
            filter_kwargs['opportunity_pipeline'] = self.opportunity_pipeline
        else:
            return None
            
        return PipelineStage.objects.filter(
            order__lt=self.order,
            is_active=True,
            **filter_kwargs
        ).order_by('-order').first()
    
    def update_overdue_status(self):
        """
        Met à jour le champ overdue basé sur la logique existante
        Réutilise la logique du BuyingProcessSubstageService
        """
        old_overdue = self.overdue
        
        # Utiliser la logique existante du service
        from ..services.buying_process_substage_service import SubstageService
        self.overdue = SubstageService._is_substage_overdue(self)
        
        # Sauvegarder seulement si le statut a changé
        if old_overdue != self.overdue:
            self.save(update_fields=['overdue'])
        
        return self.overdue
    
    def update_stakeholders(self):
        """
        Met à jour la liste des stakeholders de ce substage en agrégeant
        les contacts depuis les activités liées.
        
        Puis déclenche la mise à jour du stage parent.
        
        Cette méthode est appelée automatiquement quand :
        - Une activité est ajoutée/supprimée de ce substage
        - Les contacts d'une activité liée sont modifiés
        - Les stakeholders directs du substage sont modifiés
        """
        try:
            with transaction.atomic():
                # Récupérer tous les contacts depuis les activités liées
                all_contacts = set()
                
                # 1. Stakeholders directs (déjà dans self.stakeholders)
                direct_stakeholders = set(self.stakeholders.all())
                all_contacts.update(direct_stakeholders)
                
                # 2. Contacts depuis les activités liées à ce substage
                from ..models import SubStageActivity
                
                substage_activities = SubStageActivity.objects.filter(
                    substage=self
                ).select_related('activity')
                
                for substage_activity in substage_activities:
                    if substage_activity.activity:
                        all_contacts.update(substage_activity.activity.contacts.all())
                
                # Mettre à jour les stakeholders du substage (uniquement les ajouts depuis activités)
                current_stakeholders = set(self.stakeholders.all())
                new_stakeholders = set(all_contacts)
                
                # Ajouter les nouveaux stakeholders depuis les activités
                to_add = new_stakeholders - current_stakeholders
                if to_add:
                    self.stakeholders.add(*to_add)
                
                # Note : On ne supprime PAS automatiquement les stakeholders directs
                # car ils pourraient avoir été ajoutés manuellement
                
                # Déclencher la mise à jour du stage parent
                if self.stage:
                    self.stage.update_stakeholders()
                
                return True
                
        except Exception:
            # Log silencieux pour MVP - pas d'exception levée pour éviter les boucles
            return False

    def get_all_stakeholders(self):
        """
        Retourne tous les stakeholders de ce substage (pour lecture seule).
        """
        return self.stakeholders.all()

    def get_stakeholders_count(self):
        """
        Retourne le nombre de stakeholders dans ce substage.
        """
        return self.stakeholders.count()

    @classmethod
    def create_from_template(cls, template_stage, opportunity_pipeline, user=None):
        """
        ✅ MVP : Création simplifiée depuis template
        """
        new_stage = cls.objects.create(
            opportunity_pipeline=opportunity_pipeline,
            name=template_stage.name,
            description=template_stage.description,
            order=template_stage.order,
            is_active=template_stage.is_active,
            estimated_duration=template_stage.estimated_duration,
            status=cls.StageStatus.ACTIVE,
            client_id=opportunity_pipeline.client_id,
            created_by=user,
            updated_by=user
        )
        
        # ✅ MVP : Pas de gestion automatique des linked lists
        return new_stage

    @classmethod
    def reorder_stages(cls, stages_with_new_orders, context_filter):
        """
        ✅ MVP : Réordonnement en batch simple
        """
        for stage_id, new_order in stages_with_new_orders:
            cls.objects.filter(
                id=stage_id, 
                **context_filter
            ).update(order=new_order)

    def insert_at_position(self, new_order):
        """
        ✅ MVP : Insertion simple - conflits gérés manuellement côté frontend
        """
        self.order = new_order
        self.save()

    def mark_as_started(self):
        """
        ✅ Marque l'étape comme commencée
        """
        if self.is_opportunity_stage and not self.started_at:
            from django.utils import timezone
            self.started_at = timezone.now()
            self.status = self.StageStatus.ACTIVE
            self.save(update_fields=['started_at', 'status'])

    def mark_as_completed(self):
        """
        ✅ Marque l'étape comme terminée
        """
        if self.is_opportunity_stage:
            from django.utils import timezone
            self.completed_at = timezone.now()
            self.status = self.StageStatus.COMPLETED
            self.save(update_fields=['completed_at', 'status'])

    def mark_as_skipped(self):
        """
        ✅ Marque l'étape comme ignorée
        """
        if self.is_opportunity_stage:
            self.status = self.StageStatus.SKIPPED
            self.save(update_fields=['status'])

    def mark_as_blocked(self):
        """
        ✅ Marque l'étape comme bloquée
        """
        if self.is_opportunity_stage:
            self.status = self.StageStatus.BLOCKED
            self.save(update_fields=['status'])

    def mark_as_not_started(self):
        """
        Remet le substage à l'état non commencé
        """
        self.actual_start_date = None
        self.actual_end_date = None
        self.status = self.SubStageStatus.NOT_STARTED
        self.save(update_fields=['actual_start_date', 'actual_end_date', 'status'])

    def insert_at_position(self, new_order):
        """
        Insère ce substage à une nouvelle position en décalant les autres
        """
        old_order = self.order
        self.order = new_order
        self.save()  # La méthode save() gère automatiquement les conflits

    @classmethod
    def reorder_substages(cls, substages_with_new_orders, stage):
        """
        Réordonne plusieurs substages en une seule opération
        substages_with_new_orders: [(substage_id, new_order), ...]
        stage: PipelineStage parent
        """
        for substage_id, new_order in substages_with_new_orders:
            substage = cls.objects.get(id=substage_id, stage=stage)
            substage.order = new_order
            substage.save()

    @property
    def is_overdue(self):
        """
        Vérifie si le substage est en retard
        """
        if not self.end_date or self.status == self.SubStageStatus.COMPLETED:
            return False
        
        from django.utils import timezone
        return timezone.now().date() > self.end_date

    @property
    def days_remaining(self):
        """
        Calcule le nombre de jours restants
        """
        if not self.end_date or self.status == self.SubStageStatus.COMPLETED:
            return None
        
        from django.utils import timezone
        today = timezone.now().date()
        return (self.end_date - today).days

    @property
    def is_client_interaction(self):
        """
        Vérifie si c'est une interaction client
        """
        return self.substage_type == self.SubStageType.INTERACTION_CLIENT

    @property
    def is_internal_client_process(self):
        """
        Vérifie si c'est un processus interne client
        """
        return self.substage_type == self.SubStageType.PROCESS_INTERNE_CLIENT

    @property
    def is_internal_action(self):
        """
        Vérifie si c'est une action interne
        """
        return self.substage_type == self.SubStageType.ACTION_INTERNE
    
     # ===== MÉTHODES DE MISE À JOUR EN BATCH =====
    
    @classmethod
    def bulk_update_overdue_for_stage(cls, stage_id, client_id):
        """
        Met à jour le statut overdue de toutes les substages d'un stage en batch
        
        Args:
            stage_id: ID du PipelineStage parent
            client_id: ID du client
            
        Returns:
            dict: Résumé des mises à jour
        """
        from ..services.buying_process_substage_service import BuyingProcessSubstageService
        
        # Récupérer toutes les substages du stage
        substages = cls.objects.filter(
            stage_id=stage_id,
            client_id=client_id,
            is_active=True
        ).select_related('stage')
        
        substages_to_update = []
        updated_count = 0
        
        for substage in substages:
            old_overdue = substage.overdue
            new_overdue = BuyingProcessSubstageService._is_substage_overdue(substage)
            
            # Ajouter à la liste si le statut a changé
            if old_overdue != new_overdue:
                substage.overdue = new_overdue
                substages_to_update.append(substage)
                updated_count += 1
        
        # Mise à jour en batch si nécessaire
        if substages_to_update:
            cls.objects.bulk_update(substages_to_update, ['overdue'])
        
        return {
            'total_substages': substages.count(),
            'updated_substages': updated_count,
            'overdue_substages': sum(1 for substage in substages_to_update if substage.overdue)
        }
    
    @classmethod
    def bulk_update_overdue_for_opportunity(cls, opportunity_pipeline_id, client_id):
        """
        Met à jour le statut overdue de toutes les substages d'une opportunité en batch
        
        Args:
            opportunity_pipeline_id: ID de l'OpportunityPipeline
            client_id: ID du client
            
        Returns:
            dict: Résumé des mises à jour groupées par stage
        """
        from ..services.buying_process_substage_service import SubstageService
        
        # Récupérer toutes les substages de l'opportunité
        substages = cls.objects.filter(
            stage__opportunity_pipeline_id=opportunity_pipeline_id,
            client_id=client_id,
            is_active=True
        ).select_related('stage')
        
        # Grouper par stage
        stages_results = {}
        substages_to_update = []
        total_updated = 0
        
        # Grouper les substages par stage
        substages_by_stage = {}
        for substage in substages:
            stage_id = substage.stage_id
            if stage_id not in substages_by_stage:
                substages_by_stage[stage_id] = []
            substages_by_stage[stage_id].append(substage)
        
        # Traiter chaque groupe de substages
        for stage_id, stage_substages in substages_by_stage.items():
            stage_updated = 0
            stage_overdue = 0
            
            for substage in stage_substages:
                old_overdue = substage.overdue
                new_overdue = SubstageService._is_substage_overdue(substage)
                
                # Ajouter à la liste si le statut a changé
                if old_overdue != new_overdue:
                    substage.overdue = new_overdue
                    substages_to_update.append(substage)
                    stage_updated += 1
                    total_updated += 1
                
                if new_overdue:
                    stage_overdue += 1
            
            stages_results[stage_id] = {
                'total_substages': len(stage_substages),
                'updated_substages': stage_updated,
                'overdue_substages': stage_overdue
            }
        
        # Mise à jour en batch si nécessaire
        if substages_to_update:
            cls.objects.bulk_update(substages_to_update, ['overdue'])
        
        return {
            'total_substages': substages.count(),
            'total_updated_substages': total_updated,
            'total_overdue_substages': sum(1 for substage in substages_to_update if substage.overdue),
            'stages_details': stages_results
        }
    
    @classmethod
    def bulk_update_overdue_for_client(cls, client_id):
        """
        Met à jour le statut overdue de toutes les substages d'un client en batch
        
        Args:
            client_id: ID du client
            
        Returns:
            dict: Résumé des mises à jour par opportunité et stage
        """
        from django.db.models import Q
        
        # Récupérer toutes les substages actives du client
        substages = cls.objects.filter(
            client_id=client_id,
            is_active=True,
            stage__opportunity_pipeline__isnull=False  # Seulement les substages d'opportunité
        ).select_related('stage', 'stage__opportunity_pipeline')
        
        # Grouper par opportunité
        opportunities = {}
        for substage in substages:
            opp_id = substage.stage.opportunity_pipeline_id
            if opp_id not in opportunities:
                opportunities[opp_id] = []
            opportunities[opp_id].append(substage)
        
        # Mettre à jour chaque opportunité
        results = {}
        total_updated = 0
        
        for opp_id, opp_substages in opportunities.items():
            result = cls._bulk_update_substages_list(opp_substages)
            results[opp_id] = result
            total_updated += result['updated_substages']
        
        return {
            'total_opportunities': len(opportunities),
            'total_updated_substages': total_updated,
            'opportunities_details': results
        }
    
    @classmethod
    def _bulk_update_substages_list(cls, substages_list):
        """
        Méthode utilitaire pour mettre à jour une liste de substages
        
        Args:
            substages_list: Liste des substages à mettre à jour
            
        Returns:
            dict: Résumé des mises à jour
        """
        from ..services.buying_process_substage_service import SubstageService
        
        substages_to_update = []
        updated_count = 0
        
        for substage in substages_list:
            old_overdue = substage.overdue
            new_overdue = SubstageService._is_substage_overdue(substage)
            
            # Ajouter à la liste si le statut a changé
            if old_overdue != new_overdue:
                substage.overdue = new_overdue
                substages_to_update.append(substage)
                updated_count += 1
        
        # Mise à jour en batch si nécessaire
        if substages_to_update:
            cls.objects.bulk_update(substages_to_update, ['overdue'])
        
        return {
            'total_substages': len(substages_list),
            'updated_substages': updated_count,
            'overdue_substages': sum(1 for substage in substages_to_update if substage.overdue)
        }
    
    @classmethod
    def get_overdue_summary_for_client(cls, client_id):
        """
        Récupère un résumé des substages en retard pour un client
        
        Args:
            client_id: ID du client
            
        Returns:
            dict: Résumé détaillé des retards
        """
        substages = cls.objects.filter(
            client_id=client_id,
            is_active=True,
            stage__opportunity_pipeline__isnull=False
        ).select_related('stage', 'stage__opportunity_pipeline')
        
        total_substages = substages.count()
        overdue_substages = substages.filter(overdue=True).count()
        
        # Grouper par type de substage
        by_type = {}
        for substage_type in cls.SubStageType.choices:
            type_code = substage_type[0]
            type_substages = substages.filter(substage_type=type_code)
            type_overdue = type_substages.filter(overdue=True).count()
            
            by_type[type_code] = {
                'total': type_substages.count(),
                'overdue': type_overdue,
                'overdue_percentage': round((type_overdue / type_substages.count() * 100), 2) if type_substages.count() > 0 else 0
            }
        
        # Grouper par opportunité
        opportunities_with_overdue = substages.filter(overdue=True).values_list(
            'stage__opportunity_pipeline_id', flat=True
        ).distinct().count()
        
        total_opportunities = substages.values_list(
            'stage__opportunity_pipeline_id', flat=True
        ).distinct().count()
        
        return {
            'total_substages': total_substages,
            'overdue_substages': overdue_substages,
            'overdue_percentage': round((overdue_substages / total_substages * 100), 2) if total_substages > 0 else 0,
            'by_substage_type': by_type,
            'total_opportunities': total_opportunities,
            'opportunities_with_overdue': opportunities_with_overdue,
            'opportunities_overdue_percentage': round((opportunities_with_overdue / total_opportunities * 100), 2) if total_opportunities > 0 else 0
        }
    
    @classmethod
    def get_overdue_substages_for_client(cls, client_id, limit=None):
        """
        Récupère la liste des substages en retard pour un client
        
        Args:
            client_id: ID du client
            limit: Limite du nombre de résultats (optionnel)
            
        Returns:
            QuerySet: Substages en retard ordonnées par priorité
        """
        queryset = cls.objects.filter(
            client_id=client_id,
            is_active=True,
            overdue=True,
            stage__opportunity_pipeline__isnull=False
        ).select_related(
            'stage', 
            'stage__opportunity_pipeline',
            'stage__opportunity_pipeline__opportunity'
        ).order_by(
            'stage__opportunity_pipeline__opportunity__expected_close_date',  # Priorité aux deals qui ferment bientôt
            'stage__order',  # Puis par ordre de stage
            'order'  # Puis par ordre de substage
        )
        
        if limit:
            queryset = queryset[:limit]
            
        return queryset