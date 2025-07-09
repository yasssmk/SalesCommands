# backend/apps/opportunities/config/pipeline_stages.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class PipelineStagesConfig:
    """
    Configuration centralisée des étapes de pipeline
    """
    
    # ========== CONSTANTES STATUS ET TYPES ==========
    
    class StageStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        COMPLETED = 'COMPLETED', _('Completed')
        SKIPPED = 'SKIPPED', _('Skipped')
        BLOCKED = 'BLOCKED', _('Blocked')
    
    class SubStageType(models.TextChoices):
        INTERACTION_CLIENT = 'INTERACTION_CLIENT', _('Client Interaction')
        PROCESS_INTERNE_CLIENT = 'PROCESS_INTERNE_CLIENT', _('Internal Client Process')
        ACTION_INTERNE = 'ACTION_INTERNE', _('Internal Action')
    
    class SubStageStatus(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', _('Not Started')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        BLOCKED = 'BLOCKED', _('Blocked')
    
    class PipelineStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        COMPLETED = 'COMPLETED', _('Completed')
        PAUSED = 'PAUSED', _('Paused')
        CANCELLED = 'CANCELLED', _('Cancelled')
        FAILED = 'FAILED', _('Failed')
    
    
    # ========== ÉTAPES PAR DÉFAUT ==========
    
    # Étapes par défaut du processus de vente standard
    DEFAULT_STAGES = [
        ("Qualification", "Qualification du prospect et du besoin", 1),
        ("Technical Validation", "Validation technique de la solution", 2),
        ("Solution Validation", "Validation de la solution proposée", 3),
        ("Contract Validation", "Validation contractuelle et négociation", 4),
        ("Firming", "Finalisation et signature du contrat", 5),
    ]
    
    
    RENEWAL_STAGES = [
        ("Renewal Planning", "Planification du renouvellement", 1),
        ("Usage Review", "Revue d'usage", 2),
        ("Value Demonstration", "Démonstration de la valeur", 3),
        ("Expansion Discussion", "Discussion d'expansion", 4),
        ("Contract Renewal", "Renouvellement du contrat", 5),
    ]
    
    # ========== MÉTHODES UTILITAIRES ==========
    
    @classmethod
    def get_default_stages(cls):
        """Retourne les étapes par défaut"""
        return cls.DEFAULT_STAGES
    
    @classmethod
    def get_renewal_stages(cls):
        """Retourne les étapes pour renouvellements"""
        return cls.RENEWAL_STAGES
    
    @classmethod
    def get_stage_status_choices(cls):
        """Retourne les choix de statut pour les étapes"""
        return cls.StageStatus.choices
    
    @classmethod
    def get_substage_type_choices(cls):
        """Retourne les choix de type pour les sous-étapes"""
        return cls.SubStageType.choices
    
    @classmethod
    def get_substage_status_choices(cls):
        """Retourne les choix de statut pour les sous-étapes"""
        return cls.SubStageStatus.choices