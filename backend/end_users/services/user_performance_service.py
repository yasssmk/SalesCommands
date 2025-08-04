# apps/end_users/services/user_performance_service.py

from django.db import models
from django.db.models import Count, Sum, Q, F, Value, IntegerField, DecimalField
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Union
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class UserPerformanceService:
    """
    Service centralisé pour récupérer les métriques de performance utilisateur.
    
    Utilise des requêtes SQL optimisées avec JOINs pour éviter N+1 queries.
    Toutes les méthodes sont thread-safe et respectent le client_scope.
    """
    
    @classmethod
    def get_user_complete_performance(
        cls, 
        user_id: Union[str, int], 
        period_start: date, 
        period_end: date, 
        client_id: str
    ) -> Dict:
        """
        Récupère toutes les métriques de performance d'un utilisateur sur une période.
        
        Requête SQL optimisée qui récupère en une fois :
        - Leads créés/convertis 
        - Opportunités ouvertes/fermées/pipeline
        - Campagnes menées et résultats
        - Meetings programmés
        
        Args:
            user_id: ID de l'utilisateur
            period_start: Début de période (date)
            period_end: Fin de période (date) 
            client_id: ID client pour multi-tenant
            
        Returns:
            Dict avec toutes les métriques structurées
            
        Raises:
            StandardizedValidationError: Si utilisateur introuvable ou données incohérentes
        """
        try:
            from end_users.models import User
            
            # Valider l'utilisateur et le client_scope
            user = cls._validate_user_access(user_id, client_id)
            
            # Préparer les filtres temporels
            period_filter = Q(created_at__date__range=[period_start, period_end])
            
            # === REQUÊTE OPTIMISÉE LEADS ===
            leads_metrics = cls._get_leads_metrics(user_id, period_filter, client_id)
            
            # === REQUÊTE OPTIMISÉE OPPORTUNITIES ===
            opportunities_metrics = cls._get_opportunities_metrics(user_id, period_filter, client_id)
            
            # === REQUÊTE OPTIMISÉE CAMPAIGNS ===
            campaigns_metrics = cls._get_campaigns_metrics(user_id, period_filter, client_id)
            
            # === REQUÊTE OPTIMISÉE MEETINGS (via Activities) ===
            meetings_metrics = cls._get_meetings_metrics(user_id, period_filter, client_id)
            
            # === ASSEMBLAGE FINAL ===
            performance_data = {
                'user_info': {
                    'user_id': str(user.id),
                    'full_name': user.get_full_name(),
                    'email': user.email,
                    'team': user.team.name if user.team else None,
                    'organization': user.organization.name if user.organization else None
                },
                'period': {
                    'start_date': period_start.isoformat(),
                    'end_date': period_end.isoformat(),
                    'days_count': (period_end - period_start).days + 1
                },
                'leads': leads_metrics,
                'opportunities': opportunities_metrics, 
                'campaigns': campaigns_metrics,
                'meetings': meetings_metrics,
                'summary': cls._calculate_performance_summary(
                    leads_metrics, opportunities_metrics, campaigns_metrics, meetings_metrics
                ),
                'calculation_timestamp': timezone.now().isoformat()
            }
            
            return performance_data
            
        except Exception as e:
            if isinstance(e, StandardizedValidationError):
                raise
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to calculate user performance: {str(e)}"
                )
            )
    
    @classmethod
    def get_team_consolidated_performance(
        cls,
        team_user_ids: List[Union[str, int]],
        period_start: date,
        period_end: date, 
        client_id: str
    ) -> Dict:
        """
        Récupère les performances consolidées d'une équipe.
        
        Optimisé pour les managers : une seule requête par type de métrique
        pour tous les utilisateurs de l'équipe.
        
        Args:
            team_user_ids: Liste des IDs utilisateurs de l'équipe
            period_start: Début période
            period_end: Fin période
            client_id: ID client
            
        Returns:
            Dict avec métriques agrégées + détail par utilisateur
        """
        try:
            if not team_user_ids:
                return cls._empty_team_performance()
            
            # Récupérer les performances individuelles
            individual_performances = []
            for user_id in team_user_ids:
                try:
                    perf = cls.get_user_complete_performance(
                        user_id, period_start, period_end, client_id
                    )
                    individual_performances.append(perf)
                except StandardizedValidationError:
                    # Ignorer les utilisateurs inaccessibles
                    continue
            
            if not individual_performances:
                return cls._empty_team_performance()
            
            # Agréger les métriques équipe
            team_summary = cls._aggregate_team_metrics(individual_performances)
            
            return {
                'team_summary': team_summary,
                'individual_performances': individual_performances,
                'period': {
                    'start_date': period_start.isoformat(),
                    'end_date': period_end.isoformat(),
                    'days_count': (period_end - period_start).days + 1
                },
                'team_size': len(individual_performances),
                'calculation_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to calculate team performance: {str(e)}"
                )
            )
    
    @classmethod
    def get_user_quota_performance(
        cls,
        user_id: Union[str, int],
        quota_id: Union[str, int],
        client_id: str
    ) -> Dict:
        """
        Récupère la performance d'un utilisateur par rapport à un quota spécifique.
        
        Méthode légère pour le suivi des Sales Plans.
        Sera étendue quand les modèles SalesQuota seront créés.
        
        Args:
            user_id: ID utilisateur
            quota_id: ID du quota (futur modèle SalesQuota)
            client_id: ID client
            
        Returns:
            Dict avec métriques vs quota
        """
        try:
            
            user = cls._validate_user_access(user_id, client_id)
            
            return {
                'user_id': str(user.id),
                'quota_id': str(quota_id),
                'quota_performance': {
                    'current_value': 0,
                    'target_value': 0,
                    'progress_percentage': 0,
                    'gap_to_target': 0,
                    'days_remaining': 0
                },
                'status': 'MVP_PLACEHOLDER',
                'message': 'Will be implemented in Phase 2 with SalesQuota models'
            }
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to calculate quota performance: {str(e)}"
                )
            )
    
    # ===== MÉTHODES PRIVÉES POUR REQUÊTES OPTIMISÉES =====
    
    @classmethod
    def _validate_user_access(cls, user_id: Union[str, int], client_id: str):
        """Valide l'accès utilisateur avec client_scope"""
        try:
            from end_users.models import User
            return User.objects.get(
                id=user_id, 
                client_account_id=client_id
            )
        except User.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND
            )
    
    @classmethod
    def _get_leads_metrics(cls, user_id, period_filter, client_id) -> Dict:
        """Requête optimisée pour les métriques leads"""
        try:
            from apps.leads.models import Lead
            
            leads_qs = Lead.objects.filter(
                client_id=client_id
            ).filter(period_filter).filter(
                Q(created_by_id=user_id) | Q(assigned_to_id=user_id)
            )
            
            leads_metrics = leads_qs.aggregate(
                total_created=Count('id', filter=Q(created_by_id=user_id)),
                total_assigned=Count('id', filter=Q(assigned_to_id=user_id)),
                total_qualified=Count('id', filter=Q(
                    Q(created_by_id=user_id) | Q(assigned_to_id=user_id),
                    status='QUALIFIED'
                )),
                total_converted=Count('id', filter=Q(
                    Q(created_by_id=user_id) | Q(assigned_to_id=user_id),
                    status='CONVERTED'
                ))
            )
            
            # Calculer le taux de conversion
            total_processed = leads_metrics['total_created'] + leads_metrics['total_assigned']
            conversion_rate = (
                (leads_metrics['total_converted'] / total_processed * 100) 
                if total_processed > 0 else 0
            )
            
            return {
                'created_count': leads_metrics['total_created'] or 0,
                'assigned_count': leads_metrics['total_assigned'] or 0,
                'total_processed': total_processed,
                'qualified_count': leads_metrics['total_qualified'] or 0,
                'converted_count': leads_metrics['total_converted'] or 0,
                'conversion_rate_percentage': round(conversion_rate, 2)
            }
            
        except Exception:
            return cls._empty_leads_metrics()
    
    @classmethod
    def _get_opportunities_metrics(cls, user_id, period_filter, client_id) -> Dict:
        """Requête optimisée pour les métriques opportunities"""
        try:
            from apps.opportunities.models import Opportunity
            
            opps_qs = Opportunity.objects.filter(
                client_id=client_id
            ).filter(period_filter).filter(
                Q(created_by_id=user_id) | Q(deal_owner_id=user_id)
            )
            
            opps_metrics = opps_qs.aggregate(
                total_created=Count('id', filter=Q(created_by_id=user_id)),
                total_owned=Count('id', filter=Q(deal_owner_id=user_id)),
                total_won=Count('id', filter=Q(
                    Q(created_by_id=user_id) | Q(deal_owner_id=user_id),
                    status='WON'
                )),
                total_lost=Count('id', filter=Q(
                    Q(created_by_id=user_id) | Q(deal_owner_id=user_id),
                    status='LOST'
                )),
                pipeline_value=Sum('amount', filter=Q(
                    Q(created_by_id=user_id) | Q(deal_owner_id=user_id),
                    status='OPEN'
                )),
                won_value=Sum('amount', filter=Q(
                    Q(created_by_id=user_id) | Q(deal_owner_id=user_id),
                    status='WON'
                ))
            )
            
            # Calculer les taux
            total_closed = (opps_metrics['total_won'] or 0) + (opps_metrics['total_lost'] or 0)
            win_rate = (
                (opps_metrics['total_won'] / total_closed * 100) 
                if total_closed > 0 else 0
            )
            
            return {
                'created_count': opps_metrics['total_created'] or 0,
                'owned_count': opps_metrics['total_owned'] or 0,
                'won_count': opps_metrics['total_won'] or 0,
                'lost_count': opps_metrics['total_lost'] or 0,
                'open_count': (opps_metrics['total_owned'] or 0) - total_closed,
                'pipeline_value': float(opps_metrics['pipeline_value'] or 0),
                'won_value': float(opps_metrics['won_value'] or 0),
                'win_rate_percentage': round(win_rate, 2)
            }
            
        except Exception:
            return cls._empty_opportunities_metrics()
    
    @classmethod
    def _get_campaigns_metrics(cls, user_id, period_filter, client_id) -> Dict:
        """Requête optimisée pour les métriques campaigns"""
        try:
            from apps.campaign.models import Campaign
            
            campaigns_qs = Campaign.objects.filter(
                client_id=client_id
            ).filter(period_filter).filter(
                Q(created_by_id=user_id) | Q(owner_id=user_id)
            )
            
            campaigns_metrics = campaigns_qs.aggregate(
                total_created=Count('id', filter=Q(created_by_id=user_id)),
                total_owned=Count('id', filter=Q(owner_id=user_id)),
                active_campaigns=Count('id', filter=Q(
                    Q(created_by_id=user_id) | Q(owner_id=user_id),
                    status='ACTIVE'
                )),
                completed_campaigns=Count('id', filter=Q(
                    Q(created_by_id=user_id) | Q(owner_id=user_id),
                    status='COMPLETED'
                ))
            )
            
            return {
                'created_count': campaigns_metrics['total_created'] or 0,
                'owned_count': campaigns_metrics['total_owned'] or 0,
                'active_count': campaigns_metrics['active_campaigns'] or 0,
                'completed_count': campaigns_metrics['completed_campaigns'] or 0,
                'total_managed': (campaigns_metrics['total_created'] or 0) + (campaigns_metrics['total_owned'] or 0)
            }
            
        except Exception:
            return cls._empty_campaigns_metrics()
    
    @classmethod
    def _get_meetings_metrics(cls, user_id, period_filter, client_id) -> Dict:
        """Requête optimisée pour les métriques meetings via Activities"""
        try:
            from apps.activities.models import Activity
            
            meetings_qs = Activity.objects.filter(
                client_id=client_id,
                activity_type='MEETING'
            ).filter(period_filter).filter(
                Q(owner_id=user_id) | Q(created_by_id=user_id)
            )
            
            meetings_metrics = meetings_qs.aggregate(
                total_created=Count('id', filter=Q(created_by_id=user_id)),
                total_owned=Count('id', filter=Q(owner_id=user_id)),
                completed_meetings=Count('id', filter=Q(
                    Q(owner_id=user_id) | Q(created_by_id=user_id),
                    status='COMPLETED'
                )),
                scheduled_meetings=Count('id', filter=Q(
                    Q(owner_id=user_id) | Q(created_by_id=user_id),
                    status='SCHEDULED'
                ))
            )
            
            return {
                'created_count': meetings_metrics['total_created'] or 0,
                'owned_count': meetings_metrics['total_owned'] or 0,
                'completed_count': meetings_metrics['completed_meetings'] or 0,
                'scheduled_count': meetings_metrics['scheduled_meetings'] or 0,
                'total_managed': (meetings_metrics['total_created'] or 0) + (meetings_metrics['total_owned'] or 0)
            }
            
        except Exception:
            return cls._empty_meetings_metrics()
    
    @classmethod
    def _calculate_performance_summary(cls, leads, opportunities, campaigns, meetings) -> Dict:
        """Calcule un résumé de performance global"""
        return {
            'total_activities': (
                leads['total_processed'] + 
                opportunities['created_count'] +
                campaigns['total_managed'] +
                meetings['total_managed']
            ),
            'conversion_efficiency': {
                'leads_to_opportunities': leads['conversion_rate_percentage'],
                'opportunities_win_rate': opportunities['win_rate_percentage']
            },
            'revenue_impact': {
                'pipeline_value': opportunities['pipeline_value'],
                'closed_value': opportunities['won_value']
            },
            'activity_balance': {
                'prospecting_ratio': leads['total_processed'] / max(1, leads['total_processed'] + opportunities['created_count']) * 100,
                'closing_ratio': opportunities['won_count'] / max(1, opportunities['created_count']) * 100
            }
        }
    
    # ===== MÉTHODES HELPER POUR DONNÉES VIDES =====
    
    @classmethod
    def _empty_leads_metrics(cls) -> Dict:
        return {
            'created_count': 0, 'assigned_count': 0, 'total_processed': 0,
            'qualified_count': 0, 'converted_count': 0, 'conversion_rate_percentage': 0
        }
    
    @classmethod
    def _empty_opportunities_metrics(cls) -> Dict:
        return {
            'created_count': 0, 'owned_count': 0, 'won_count': 0, 'lost_count': 0,
            'open_count': 0, 'pipeline_value': 0, 'won_value': 0, 'win_rate_percentage': 0
        }
    
    @classmethod
    def _empty_campaigns_metrics(cls) -> Dict:
        return {
            'created_count': 0, 'owned_count': 0, 'active_count': 0, 
            'completed_count': 0, 'total_managed': 0
        }
    
    @classmethod
    def _empty_meetings_metrics(cls) -> Dict:
        return {
            'created_count': 0, 'owned_count': 0, 'completed_count': 0,
            'scheduled_count': 0, 'total_managed': 0
        }
    
    @classmethod
    def _empty_team_performance(cls) -> Dict:
        return {
            'team_summary': {}, 'individual_performances': [],
            'team_size': 0, 'message': 'No accessible team members found'
        }
    
    @classmethod
    def _aggregate_team_metrics(cls, individual_performances: List[Dict]) -> Dict:
        """Agrège les métriques individuelles en métriques équipe"""
        if not individual_performances:
            return {}
        
        # Agréger toutes les métriques
        team_totals = {
            'leads': cls._empty_leads_metrics(),
            'opportunities': cls._empty_opportunities_metrics(), 
            'campaigns': cls._empty_campaigns_metrics(),
            'meetings': cls._empty_meetings_metrics()
        }
        
        for perf in individual_performances:
            for category in ['leads', 'opportunities', 'campaigns', 'meetings']:
                for metric, value in perf[category].items():
                    if isinstance(value, (int, float)):
                        team_totals[category][metric] += value
        
        # Recalculer les ratios pour l'équipe
        team_totals['leads']['conversion_rate_percentage'] = (
            (team_totals['leads']['converted_count'] / max(1, team_totals['leads']['total_processed'])) * 100
        )
        
        team_totals['opportunities']['win_rate_percentage'] = (
            (team_totals['opportunities']['won_count'] / 
             max(1, team_totals['opportunities']['won_count'] + team_totals['opportunities']['lost_count'])) * 100
        )
        
        return team_totals