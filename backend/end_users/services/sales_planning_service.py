# apps/core_apps/services/sales_planning_service.py

from django.utils import timezone
from django.db.models import Q
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from .user_performance_service import UserPerformanceService


class SalesPlanningService:
    """
    Service centralisé pour la planification commerciale.
    
    Architecture MVP avec logique générique qui fonctionne pour:
    - Tous types de quotas (closed_won, pipeline, meetings, leads_accepted)
    - Tous types de milestones (LEADS_GENERATED, PIPELINE_VALUE, etc.)
    - Timeline flexible avec calculs automatiques previous/next
    - Dimension temporelle complète (jours restants, rythme nécessaire)
    
    CORRECTIONS CRITIQUES :
    - Signature UserPerformanceService corrigée
    - Mapping métriques corrigé selon vraie structure
    - Extraction des valeurs selon performance_data réelle
    
    Usage:
        analysis = SalesPlanningService.generate_complete_analysis(sales_plan)
    """
    
    # === CONFIGURATION CORRIGÉE DES TYPES ===
    
    @classmethod
    def _get_metric_value_from_performance(
        cls, 
        metric_type: str, 
        performance_data: Dict[str, Any], 
        custom_logic=None
    ) -> float:
        """
        ✅ NOUVEAU : Extraction unifiée selon la vraie structure UserPerformanceService
        
        Remplace l'ancien METRIC_MAPPINGS qui était totalement incorrect.
        
        Structure réelle UserPerformanceService :
        {
            'leads': {'qualified_count': ..., 'converted_count': ...},
            'opportunities': {'created_count': ..., 'won_value': ..., 'pipeline_value': ...},
            'meetings': {'completed_count': ..., 'total_managed': ...},
            'campaigns': {...}
        }
        """
        if metric_type == 'CUSTOM' and custom_logic:
            return custom_logic(performance_data)
        
        try:
            # Mapping pour types de quota
            if metric_type == 'closed_won':
                return float(performance_data.get('opportunities', {}).get('won_value', 0))
            elif metric_type == 'pipeline':
                return float(performance_data.get('opportunities', {}).get('pipeline_value', 0))
            elif metric_type == 'meetings':
                return float(performance_data.get('meetings', {}).get('completed_count', 0))
            elif metric_type == 'leads_accepted':
                return float(performance_data.get('leads', {}).get('qualified_count', 0))
            elif metric_type == 'opportunities':
                return float(performance_data.get('opportunities', {}).get('created_count', 0))
            elif metric_type == 'conversion_rate':
                return float(performance_data.get('leads', {}).get('conversion_rate_percentage', 0))
            
            # Mapping pour types de milestone
            elif metric_type == 'LEADS_GENERATED':
                return float(performance_data.get('leads', {}).get('qualified_count', 0))
            elif metric_type == 'MEETINGS_SECURED':
                return float(performance_data.get('meetings', {}).get('completed_count', 0))
            elif metric_type == 'OPPORTUNITIES_CREATED':
                return float(performance_data.get('opportunities', {}).get('created_count', 0))
            elif metric_type == 'PIPELINE_VALUE':
                return float(performance_data.get('opportunities', {}).get('pipeline_value', 0))
            elif metric_type == 'CLOSED_WON':
                return float(performance_data.get('opportunities', {}).get('won_value', 0))
            
            else:
                return 0.0
                
        except (KeyError, TypeError, ValueError, AttributeError):
            return 0.0
    
    # Chemins de conversion logiques (inchangé - logique OK)
    CONVERSION_PATHS = [
        ('LEADS_GENERATED', 'MEETINGS_SECURED'),
        ('MEETINGS_SECURED', 'OPPORTUNITIES_CREATED'),
        ('OPPORTUNITIES_CREATED', 'PIPELINE_VALUE'),
        ('PIPELINE_VALUE', 'CLOSED_WON'),
        ('LEADS_GENERATED', 'OPPORTUNITIES_CREATED'),  # Direct
        ('MEETINGS_SECURED', 'CLOSED_WON'),  # Direct
        ('LEADS_GENERATED', 'PIPELINE_VALUE'),  # Direct
    ]
    
    @classmethod
    def generate_complete_analysis(cls, sales_plan) -> Dict[str, Any]:
        """
        Génère l'analyse complète du Sales Plan.
        Point d'entrée principal - fonctionne pour toute configuration.
        
        ✅ CORRECTION CRITIQUE : Signature UserPerformanceService corrigée
        """
        try:
            # Validation du plan
            cls._validate_sales_plan(sales_plan)
            
            # ✅ SIGNATURE CORRIGÉE - UserPerformanceService
            performance_data = UserPerformanceService.get_user_complete_performance(
                user_id=sales_plan.user.id,  # ✅ Corrigé : user_id au lieu de user
                period_start=sales_plan.period_start,
                period_end=sales_plan.period_end,
                client_id=sales_plan.client_id  # ✅ Ajouté : client_id manquant
            )
            
            # Analyse temporelle (inchangé - logique OK)
            time_analysis = cls._calculate_time_analysis(sales_plan)
            
            # Timeline des milestones (corrigé pour utiliser nouveau mapping)
            timeline_analysis = cls._analyze_complete_timeline(sales_plan, performance_data, time_analysis)
            
            # Contribution des campagnes (inchangé)
            campaigns_contribution = cls._get_campaigns_contribution(sales_plan)
            
            # ✅ ANALYSE QUOTA CORRIGÉE avec nouveau mapping
            quota_analysis = cls._analyze_main_quota(sales_plan, performance_data, time_analysis)
            
            return {
                'plan_summary': {
                    'id': sales_plan.id,
                    'name': sales_plan.name,
                    'status': sales_plan.status,
                    'user_id': sales_plan.user.id,
                    'period_start': sales_plan.period_start.isoformat(),
                    'period_end': sales_plan.period_end.isoformat()
                },
                'time_analysis': time_analysis,
                'quota_analysis': quota_analysis,
                'timeline_analysis': timeline_analysis,
                'campaigns_contribution': campaigns_contribution,
                'generated_at': timezone.now().isoformat(),
                'data_source': 'UserPerformanceService_v2_corrected'  # ✅ Marqueur version corrigée
            }
            
        except Exception as e:
            # ✅ Gestion d'erreur améliorée
            return cls._get_fallback_analysis(sales_plan, str(e))
    
    @classmethod
    def _validate_sales_plan(cls, sales_plan):
        """Validation basique du Sales Plan (inchangé)"""
        if not sales_plan:
            raise StandardizedValidationError("Sales Plan is required")
        
        if not sales_plan.quota:
            raise StandardizedValidationError("Sales Plan must have an active quota")
        
        if not sales_plan.user:
            raise StandardizedValidationError("Sales Plan must have an assigned user")
    
    @classmethod
    def _calculate_time_analysis(cls, sales_plan) -> Dict[str, Any]:
        """
        Calcule l'analyse temporelle complète. (INCHANGÉ - logique correcte)
        Dimension temps : où on en est, combien reste-t-il, rythme nécessaire.
        """
        today = timezone.now().date()
        period_start = sales_plan.period_start
        period_end = sales_plan.period_end
        
        # Calculs de base
        total_days = (period_end - period_start).days + 1
        days_elapsed = max(0, (today - period_start).days)
        days_remaining = max(0, (period_end - today).days)
        
        # Pourcentages temporels
        time_elapsed_percentage = (days_elapsed / total_days) * 100 if total_days > 0 else 0
        time_remaining_percentage = (days_remaining / total_days) * 100 if total_days > 0 else 0
        
        # Statut temporel
        if today < period_start:
            time_status = 'NOT_STARTED'
        elif today > period_end:
            time_status = 'EXPIRED'
        else:
            time_status = 'ACTIVE'
        
        # Semaines
        weeks_elapsed = days_elapsed // 7
        weeks_remaining = days_remaining // 7
        
        return {
            'current_date': today.isoformat(),
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'total_days': total_days,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'weeks_elapsed': weeks_elapsed,
            'weeks_remaining': weeks_remaining,
            'time_elapsed_percentage': round(time_elapsed_percentage, 2),
            'time_remaining_percentage': round(time_remaining_percentage, 2),
            'time_status': time_status,
            'is_active_period': time_status == 'ACTIVE'
        }
    
    @classmethod
    def _get_current_value_generic(cls, metric_type: str, performance_data: Dict[str, Any], custom_logic=None) -> float:
        """
        ✅ MÉTHODE CORRIGÉE : Utilise maintenant le nouveau mapping
        Ancienne version utilisait METRIC_MAPPINGS incorrect
        """
        return cls._get_metric_value_from_performance(metric_type, performance_data, custom_logic)
    
    @classmethod
    def _build_milestone_timeline(cls, sales_plan) -> List[Dict[str, Any]]:
        """
        Construit la chronologie avec liens previous/next. (INCHANGÉ - logique correcte)
        Indépendant du type de milestone - pure logique temporelle.
        """
        milestones = list(sales_plan.milestones.order_by('target_date'))
        timeline = []
        
        for i, milestone in enumerate(milestones):
            previous_milestone = milestones[i-1] if i > 0 else None
            next_milestone = milestones[i+1] if i < len(milestones)-1 else None
            
            timeline.append({
                'milestone': milestone,
                'position': i + 1,  # Position humaine (1, 2, 3...)
                'previous': previous_milestone,
                'next': next_milestone,
                'is_first': i == 0,
                'is_last': i == len(milestones) - 1,
                'total_milestones': len(milestones)
            })
        
        return timeline
    
    @classmethod
    def _calculate_milestone_gap(cls, milestone_info: Dict[str, Any], performance_data: Dict[str, Any], time_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ CORRIGÉ : Calcul générique du gap pour chaque milestone avec dimension temporelle.
        Utilise maintenant le mapping corrigé.
        """
        milestone = milestone_info['milestone']
        
        # ✅ Utilise le nouveau mapping corrigé
        current_value = cls._get_current_value_generic(
            milestone.milestone_type, 
            performance_data
        )
        
        # Gap de base
        gap = float(milestone.target_value) - current_value
        gap_percentage = (gap / float(milestone.target_value)) * 100 if milestone.target_value > 0 else 0
        achievement_rate = (current_value / float(milestone.target_value)) * 100 if milestone.target_value > 0 else 0
        
        # Analyse temporelle du milestone
        today = timezone.now().date()
        days_to_milestone = max(0, (milestone.target_date - today).days)
        is_overdue = milestone.target_date < today
        
        # Rythme nécessaire
        daily_pace_needed = gap / max(1, days_to_milestone) if gap > 0 and days_to_milestone > 0 else 0
        weekly_pace_needed = daily_pace_needed * 7
        
        # Statut du milestone
        if achievement_rate >= 100:
            milestone_status = 'ACHIEVED'
        elif is_overdue:
            milestone_status = 'OVERDUE'
        elif days_to_milestone <= 7:
            milestone_status = 'URGENT'
        else:
            milestone_status = 'ON_TRACK'
        
        return {
            'milestone_id': milestone.id,
            'milestone_name': milestone.name,
            'milestone_type': milestone.milestone_type,
            'target_date': milestone.target_date.isoformat(),
            'target_value': float(milestone.target_value),
            'current_value': current_value,
            'gap_value': max(0, gap),
            'gap_percentage': round(gap_percentage, 2),
            'achievement_rate': round(achievement_rate, 2),
            'is_achieved': gap <= 0,
            'is_overdue': is_overdue,
            'days_to_milestone': days_to_milestone,
            'milestone_status': milestone_status,
            'daily_pace_needed': round(daily_pace_needed, 2),
            'weekly_pace_needed': round(weekly_pace_needed, 2),
            'position': milestone_info['position']
        }
    
    @classmethod
    def _calculate_next_milestone_requirements(cls, milestone_info: Dict[str, Any], performance_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        ✅ CORRIGÉ : Calcule ce qu'il faut pour atteindre le prochain milestone.
        Utilise maintenant le mapping corrigé.
        """
        current_milestone = milestone_info['milestone']
        next_milestone = milestone_info['next']
        
        if not next_milestone:
            return None  # Pas de prochain milestone
        
        # ✅ Valeurs actuelles avec mapping corrigé
        current_value_now = cls._get_current_value_generic(
            current_milestone.milestone_type, 
            performance_data
        )
        next_value_now = cls._get_current_value_generic(
            next_milestone.milestone_type, 
            performance_data
        )
        
        # Gaps respectifs
        current_gap = max(0, float(current_milestone.target_value) - current_value_now)
        next_gap = max(0, float(next_milestone.target_value) - next_value_now)
        
        # Calcul du ratio de conversion (si types compatibles)
        conversion_ratio = None
        conversion_possible = cls._can_calculate_conversion(
            current_milestone.milestone_type, 
            next_milestone.milestone_type
        )
        
        if conversion_possible and current_milestone.target_value > 0:
            conversion_ratio = float(next_milestone.target_value) / float(current_milestone.target_value)
        
        # Analyse temporelle
        today = timezone.now().date()
        days_between = (next_milestone.target_date - current_milestone.target_date).days
        days_to_next = max(0, (next_milestone.target_date - today).days)
        
        # Rythme quotidien pour atteindre le prochain
        daily_pace_to_next = next_gap / max(1, days_to_next) if next_gap > 0 and days_to_next > 0 else 0
        
        return {
            'next_milestone_id': next_milestone.id,
            'next_milestone_name': next_milestone.name,
            'next_milestone_type': next_milestone.milestone_type,
            'next_target_date': next_milestone.target_date.isoformat(),
            'days_between_milestones': days_between,
            'days_to_next': days_to_next,
            'current_gap': round(current_gap, 2),
            'next_gap': round(next_gap, 2),
            'conversion_ratio': round(conversion_ratio, 4) if conversion_ratio else None,
            'conversion_possible': conversion_possible,
            'daily_pace_to_next': round(daily_pace_to_next, 2)
        }
    
    @classmethod
    def _analyze_complete_timeline(cls, sales_plan, performance_data: Dict[str, Any], time_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ CORRIGÉ : Analyse complète de la timeline - utilise mapping corrigé.
        """
        # Construction de la timeline
        timeline = cls._build_milestone_timeline(sales_plan)
        
        if not timeline:
            return {
                'timeline': [],
                'summary': {
                    'total_milestones': 0,
                    'achieved_count': 0,
                    'overdue_count': 0,
                    'remaining_count': 0
                }
            }
        
        # Analyse de chaque milestone avec mapping corrigé
        timeline_analysis = []
        achieved_count = 0
        overdue_count = 0
        
        for milestone_info in timeline:
            # ✅ Gap analysis avec mapping corrigé
            gap_analysis = cls._calculate_milestone_gap(milestone_info, performance_data, time_analysis)
            
            # ✅ Requirements avec mapping corrigé
            next_requirements = cls._calculate_next_milestone_requirements(milestone_info, performance_data)
            
            # Compteurs
            if gap_analysis['is_achieved']:
                achieved_count += 1
            elif gap_analysis['is_overdue']:
                overdue_count += 1
            
            # Consolidation
            timeline_analysis.append({
                **gap_analysis,
                'next_requirements': next_requirements,
                'is_first': milestone_info['is_first'],
                'is_last': milestone_info['is_last']
            })
        
        return {
            'timeline': timeline_analysis,
            'summary': {
                'total_milestones': len(timeline),
                'achieved_count': achieved_count,
                'overdue_count': overdue_count,
                'remaining_count': len(timeline) - achieved_count,
                'achievement_rate': round((achieved_count / len(timeline)) * 100, 2) if timeline else 0
            }
        }
    
    @classmethod
    def _analyze_main_quota(cls, sales_plan, performance_data: Dict[str, Any], time_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ CORRIGÉ : Analyse du quota principal avec mapping corrigé.
        """
        quota = sales_plan.quota
        
        # ✅ Utilise le mapping corrigé
        current_value = cls._get_current_value_generic(
            quota.target_type, 
            performance_data
        )
        
        # Gap de base
        target_value = float(quota.target_value)
        gap = target_value - current_value
        achievement_rate = (current_value / target_value) * 100 if target_value > 0 else 0
        
        # Rythme nécessaire basé sur temps restant
        days_remaining = time_analysis['days_remaining']
        daily_pace_needed = gap / max(1, days_remaining) if gap > 0 and days_remaining > 0 else 0
        weekly_pace_needed = daily_pace_needed * 7
        monthly_pace_needed = daily_pace_needed * 30
        
        # Rythme actuel (basé sur temps écoulé)
        days_elapsed = time_analysis['days_elapsed']
        current_daily_pace = current_value / max(1, days_elapsed) if days_elapsed > 0 else 0
        
        # Projection si rythme actuel maintenu
        projected_final_value = current_daily_pace * time_analysis['total_days']
        projected_achievement_rate = (projected_final_value / target_value) * 100 if target_value > 0 else 0
        
        return {
            'quota_type': quota.target_type,
            'target_value': target_value,
            'current_value': current_value,
            'gap_value': max(0, gap),
            'achievement_rate': round(achievement_rate, 2),
            'daily_pace_needed': round(daily_pace_needed, 2),
            'weekly_pace_needed': round(weekly_pace_needed, 2),
            'monthly_pace_needed': round(monthly_pace_needed, 2),
            'current_daily_pace': round(current_daily_pace, 2),
            'projected_final_value': round(projected_final_value, 2),
            'projected_achievement_rate': round(projected_achievement_rate, 2),
            'is_on_track': projected_achievement_rate >= 95,  # Seuil de 95%
            'pace_deficit': round(daily_pace_needed - current_daily_pace, 2)
        }
    
    @classmethod
    def _get_campaigns_contribution(cls, sales_plan) -> Dict[str, Any]:
        """
        Contribution des campagnes - générique pour tous types d'objectifs. (INCHANGÉ)
        """
        try:
            from apps.campaign.models import Campaign
            
            # Récupérer campaigns qui chevauchent la période du plan
            overlapping_campaigns = Campaign.objects.filter(
                Q(start_date__lte=sales_plan.period_end) &
                Q(end_date__gte=sales_plan.period_start) &
                Q(client_id=sales_plan.client_id)
            ).prefetch_related('objectives')
            
            campaigns_data = []
            contributions_by_type = {}
            
            for campaign in overlapping_campaigns:
                objectives = campaign.objectives.all()
                
                for objective in objectives:
                    # Vérifier si l'objectif contribue au quota/milestones
                    campaign_data = {
                        'campaign_name': campaign.name,
                        'campaign_id': campaign.id,
                        'objective_type': objective.target_type,
                        'target_value': float(objective.target_value),
                        'start_date': campaign.start_date.isoformat(),
                        'end_date': campaign.end_date.isoformat()
                    }
                    campaigns_data.append(campaign_data)
                    
                    # Grouper par type pour contribution totale
                    obj_type = objective.target_type
                    if obj_type not in contributions_by_type:
                        contributions_by_type[obj_type] = 0
                    contributions_by_type[obj_type] += float(objective.target_value)
            
            return {
                'campaigns_detail': campaigns_data,
                'total_contributions': contributions_by_type,
                'campaigns_count': len(set(c['campaign_id'] for c in campaigns_data))
            }
            
        except Exception:
            # Fallback silencieux en cas d'erreur
            return {
                'campaigns_detail': [],
                'total_contributions': {},
                'campaigns_count': 0
            }
    
    @classmethod
    def _can_calculate_conversion(cls, from_type: str, to_type: str) -> bool:
        """
        Détermine si on peut calculer un ratio de conversion entre 2 types. (INCHANGÉ)
        """
        return (from_type, to_type) in cls.CONVERSION_PATHS
    
    # === MÉTHODES UTILITAIRES PUBLIQUES ===
    
    @classmethod
    def get_quick_summary(cls, sales_plan) -> Dict[str, Any]:
        """
        ✅ CORRIGÉ : Résumé rapide pour dashboard - signature corrigée.
        """
        try:
            # ✅ Signature corrigée
            performance_data = UserPerformanceService.get_user_complete_performance(
                user_id=sales_plan.user.id,  # ✅ Corrigé
                period_start=sales_plan.period_start,
                period_end=sales_plan.period_end,
                client_id=sales_plan.client_id  # ✅ Ajouté
            )
            
            time_analysis = cls._calculate_time_analysis(sales_plan)
            quota_analysis = cls._analyze_main_quota(sales_plan, performance_data, time_analysis)
            
            return {
                'plan_name': sales_plan.name,
                'time_remaining_percentage': time_analysis['time_remaining_percentage'],
                'achievement_rate': quota_analysis['achievement_rate'],
                'is_on_track': quota_analysis['is_on_track'],
                'daily_pace_needed': quota_analysis['daily_pace_needed'],
                'gap_value': quota_analysis['gap_value'],
                'success': True
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'plan_name': sales_plan.name if sales_plan else 'Unknown',
                'success': False
            }
    
    # === NOUVELLES MÉTHODES DE FALLBACK ===
    
    @classmethod
    def _get_fallback_analysis(cls, sales_plan, error_message: str) -> Dict[str, Any]:
        """
        ✅ NOUVEAU : Analyse de fallback en cas d'erreur complète
        """
        try:
            time_analysis = cls._calculate_time_analysis(sales_plan)
        except Exception:
            time_analysis = {'time_remaining_percentage': 50, 'days_remaining': 0}
        
        return {
            'plan_summary': {
                'id': sales_plan.id if sales_plan else None,
                'name': sales_plan.name if sales_plan else 'Unknown',
                'status': sales_plan.status if sales_plan else 'UNKNOWN',
                'error': 'Analysis failed'
            },
            'time_analysis': time_analysis,
            'quota_analysis': {
                'achievement_rate': 0,
                'is_on_track': False,
                'gap_value': 0
            },
            'timeline_analysis': {
                'timeline': [],
                'summary': {'total_milestones': 0}
            },
            'campaigns_contribution': {
                'campaigns_detail': [],
                'campaigns_count': 0
            },
            'error': error_message,
            'generated_at': timezone.now().isoformat(),
            'data_source': 'fallback_mode'
        }