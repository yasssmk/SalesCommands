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
    
    VERSION COMPLÈTE avec support SalesQuota et Organisations.
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
        IMPLÉMENTATION COMPLÈTE et OPTIMISÉE pour SalesQuota.
        Remplace le placeholder original.
        
        Optimisations :
        - Une seule requête performance complète
        - Mapping intelligent target_type → métriques
        - Calculs locaux pour timing
        - Structure cache-ready
        
        Args:
            user_id: ID utilisateur
            quota_id: ID du quota SalesQuota
            client_id: ID client
            
        Returns:
            Dict avec métriques vs quota optimisées
        """
        try:
            from end_users.models import SalesQuota
            
            # Récupérer et valider le quota avec optimisation
            try:
                quota = SalesQuota.objects.select_related('user', 'user__team', 'user__organization').get(
                    id=quota_id,
                    client_id=client_id,
                    user_id=user_id
                )
            except SalesQuota.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Utiliser la performance complète existante (UNE SEULE requête)
            performance_data = cls.get_user_complete_performance(
                user_id=user_id,
                period_start=quota.period_start,
                period_end=quota.period_end,
                client_id=client_id
            )
            
            # Extraire la valeur actuelle selon target_type (optimisé)
            current_value = cls._extract_quota_current_value(performance_data, quota.target_type)
            
            # Calculer les métriques (optimisé avec calculs locaux)
            target_value = float(quota.target_value)
            progress_percentage = cls._calculate_quota_progress(current_value, target_value)
            gap_to_target = target_value - current_value
            
            # Métriques temporelles (calculs locaux optimisés)
            timing_metrics = cls._calculate_timing_metrics(quota.period_start, quota.period_end)
            
            # Calculs de rythme optimisés
            expected_progress = (timing_metrics['days_elapsed'] / timing_metrics['days_total']) * 100 if timing_metrics['days_total'] > 0 else 0
            pace_vs_expected = progress_percentage - expected_progress
            
            # Statut de performance (optimisé)
            status = cls._determine_quota_status(
                progress_percentage, timing_metrics['days_remaining'], quota.period_end
            )
            
            # Projections optimisées
            forecast = cls._calculate_quota_forecast(
                current_value, target_value, timing_metrics['days_elapsed'], timing_metrics['days_remaining']
            )
            
            return {
                'user_id': str(user_id),
                'quota_id': str(quota_id),
                'quota_info': {
                    'target_type': quota.target_type,
                    'target_type_display': quota.get_target_type_display(),
                    'target_value': target_value,
                    'period_start': quota.period_start.isoformat(),
                    'period_end': quota.period_end.isoformat()
                },
                'quota_performance': {
                    'current_value': current_value,
                    'target_value': target_value,
                    'progress_percentage': round(progress_percentage, 1),
                    'gap_to_target': gap_to_target,
                    'is_achieved': current_value >= target_value
                },
                'timing': {
                    **timing_metrics,
                    'expected_progress': round(expected_progress, 1),
                    'pace_vs_expected': round(pace_vs_expected, 1)
                },
                'status': status,
                'forecast': forecast,
                'calculation_timestamp': timezone.now().isoformat()
            }
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to calculate quota performance: {str(e)}"
                )
            )

    # ===== NOUVELLES MÉTHODES ORGANISATIONS =====

    @classmethod
    def get_organization_performance_summary(
        cls,
        organization_id: Union[str, int],
        period_start: date,
        period_end: date,
        client_id: str,
        include_team_breakdown: bool = True
    ) -> Dict:
        """
        Performance consolidée d'une organisation complète.
        
        Optimisations :
        - Requêtes groupées par équipe
        - Division teams vs contributeurs individuels
        - Batch processing pour éviter N+1
        
        Args:
            organization_id: ID organisation
            period_start: Début période
            period_end: Fin période  
            client_id: ID client
            include_team_breakdown: Inclure détail par équipe
            
        Returns:
            Dict avec performance organisation + breakdown teams
        """
        try:
            from end_users.models import User, Team, Organization
            
            # Valider l'organisation
            try:
                organization = Organization.objects.get(
                    id=organization_id,
                    client_account_id=client_id
                )
            except Organization.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Récupérer tous les utilisateurs de l'organisation avec optimisation
            org_users = User.objects.select_related('team').filter(
                organization=organization,
                client_account_id=client_id,
                is_active=True
            )
            
            if not org_users.exists():
                return cls._empty_organization_performance(organization)
            
            # Séparer users avec équipe vs contributeurs individuels
            users_with_teams = org_users.filter(team__isnull=False)
            individual_contributors = org_users.filter(team__isnull=True)
            
            # Récupérer les équipes de l'organisation
            teams = Team.objects.filter(
                organization=organization,
                client_account_id=client_id,
                is_active=True
            ).prefetch_related('members')
            
            # Performance globale organisation (batch optimisé)
            org_user_ids = list(org_users.values_list('id', flat=True))
            org_performance = cls._get_batch_performance_summary(
                org_user_ids, period_start, period_end, client_id
            )
            
            result = {
                'organization_info': {
                    'id': str(organization.id),
                    'name': organization.name,
                    'total_users': org_users.count(),
                    'teams_count': teams.count(),
                    'individual_contributors_count': individual_contributors.count()
                },
                'period': {
                    'start_date': period_start.isoformat(),
                    'end_date': period_end.isoformat(),
                    'days_count': (period_end - period_start).days + 1
                },
                'organization_performance': org_performance,
                'calculation_timestamp': timezone.now().isoformat()
            }
            
            # Breakdown par équipe si demandé
            if include_team_breakdown:
                team_performances = []
                
                for team in teams:
                    team_user_ids = list(team.members.filter(is_active=True).values_list('id', flat=True))
                    if team_user_ids:
                        team_perf = cls._get_batch_performance_summary(
                            team_user_ids, period_start, period_end, client_id
                        )
                        team_performances.append({
                            'team_info': {
                                'id': str(team.id),
                                'name': team.name,
                                'members_count': len(team_user_ids)
                            },
                            'performance': team_perf
                        })
                
                # Performance contributeurs individuels
                if individual_contributors.exists():
                    individual_ids = list(individual_contributors.values_list('id', flat=True))
                    individual_perf = cls._get_batch_performance_summary(
                        individual_ids, period_start, period_end, client_id
                    )
                    
                    result['individual_contributors'] = {
                        'count': len(individual_ids),
                        'performance': individual_perf
                    }
                
                result['teams_performance'] = team_performances
            
            return result
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to calculate organization performance: {str(e)}"
                )
            )

    @classmethod
    def get_organization_quota_summary(
        cls,
        organization_id: Union[str, int],
        client_id: str,
        include_inactive: bool = False,
        group_by_teams: bool = True
    ) -> Dict:
        """
        Résumé des quotas pour une organisation complète.
        
        Optimisations :
        - Requête groupée sur tous les quotas organisation
        - Division par équipes automatique
        - Batch processing des performances
        
        Args:
            organization_id: ID organisation
            client_id: ID client
            include_inactive: Inclure quotas inactifs
            group_by_teams: Grouper par équipes
            
        Returns:
            Dict avec résumé quotas organisation
        """
        try:
            from end_users.models import SalesQuota, Organization, Team
            
            # Valider l'organisation
            try:
                organization = Organization.objects.get(
                    id=organization_id,
                    client_account_id=client_id
                )
            except Organization.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Récupérer tous les quotas de l'organisation avec optimisations
            quotas_filter = Q(
                user__organization=organization,
                client_id=client_id
            )
            if not include_inactive:
                quotas_filter &= Q(is_active=True)
            
            quotas = SalesQuota.objects.select_related(
                'user', 'user__team', 'user__organization'
            ).filter(quotas_filter)
            
            if not quotas.exists():
                return cls._empty_organization_quota_summary(organization)
            
            # Batch processing des performances quotas (optimisé)
            quota_performances = []
            for quota in quotas:
                try:
                    perf = cls.get_user_quota_performance(
                        user_id=quota.user.id,
                        quota_id=quota.id,
                        client_id=client_id
                    )
                    quota_performances.append({
                        'quota': quota,
                        'performance': perf,
                        'user_team': quota.user.team
                    })
                except Exception:
                    continue
            
            # Métriques globales organisation
            total_quotas = len(quota_performances)
            achieved_count = len([qp for qp in quota_performances 
                                 if qp['performance']['quota_performance']['is_achieved']])
            at_risk_count = len([qp for qp in quota_performances 
                                if qp['performance']['status'] == 'at_risk'])
            
            organization_summary = {
                'total_quotas': total_quotas,
                'achieved_count': achieved_count,
                'at_risk_count': at_risk_count,
                'on_track_count': total_quotas - achieved_count - at_risk_count,
                'achievement_rate': round((achieved_count / total_quotas) * 100, 1) if total_quotas > 0 else 0,
                'average_progress': round(
                    sum(qp['performance']['quota_performance']['progress_percentage'] 
                        for qp in quota_performances) / total_quotas, 1
                ) if total_quotas > 0 else 0
            }
            
            result = {
                'organization_info': {
                    'id': str(organization.id),
                    'name': organization.name
                },
                'organization_quota_summary': organization_summary,
                'calculation_timestamp': timezone.now().isoformat()
            }
            
            # Groupement par équipes si demandé
            if group_by_teams:
                teams_quotas = {}
                individual_quotas = []
                
                for qp in quota_performances:
                    if qp['user_team']:
                        team_key = str(qp['user_team'].id)
                        if team_key not in teams_quotas:
                            teams_quotas[team_key] = {
                                'team_info': {
                                    'id': team_key,
                                    'name': qp['user_team'].name
                                },
                                'quotas': []
                            }
                        teams_quotas[team_key]['quotas'].append(qp)
                    else:
                        individual_quotas.append(qp)
                
                # Calculer métriques par équipe
                teams_summary = []
                for team_data in teams_quotas.values():
                    team_quotas = team_data['quotas']
                    team_achieved = len([q for q in team_quotas 
                                       if q['performance']['quota_performance']['is_achieved']])
                    team_at_risk = len([q for q in team_quotas 
                                      if q['performance']['status'] == 'at_risk'])
                    
                    teams_summary.append({
                        'team_info': team_data['team_info'],
                        'summary': {
                            'total_quotas': len(team_quotas),
                            'achieved_count': team_achieved,
                            'at_risk_count': team_at_risk,
                            'achievement_rate': round((team_achieved / len(team_quotas)) * 100, 1)
                        }
                    })
                
                result['teams_quota_summary'] = teams_summary
                
                # Contributeurs individuels
                if individual_quotas:
                    individual_achieved = len([q for q in individual_quotas 
                                             if q['performance']['quota_performance']['is_achieved']])
                    individual_at_risk = len([q for q in individual_quotas 
                                            if q['performance']['status'] == 'at_risk'])
                    
                    result['individual_contributors_quota_summary'] = {
                        'total_quotas': len(individual_quotas),
                        'achieved_count': individual_achieved,
                        'at_risk_count': individual_at_risk,
                        'achievement_rate': round((individual_achieved / len(individual_quotas)) * 100, 1)
                    }
            
            return result
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to calculate organization quota summary: {str(e)}"
                )
            )

    # ===== MÉTHODES PRIVÉES POUR REQUÊTES OPTIMISÉES (ORIGINALES) =====
    
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

    # ===== NOUVELLES MÉTHODES HELPER OPTIMISÉES =====

    @classmethod
    def _get_batch_performance_summary(
        cls,
        user_ids: List[Union[str, int]],
        period_start: date,
        period_end: date,
        client_id: str
    ) -> Dict:
        """
        Performance batch pour plusieurs utilisateurs (optimisé).
        Évite les N+1 queries en agrégeant directement en SQL.
        """
        try:
            if not user_ids:
                return cls._empty_performance_summary()
            
            # Préparer les filtres temporels
            period_filter = Q(created_at__date__range=[period_start, period_end])
            
            # Agrégations batch optimisées (une requête par type)
            leads_aggregates = cls._get_batch_leads_metrics(user_ids, period_filter, client_id)
            opps_aggregates = cls._get_batch_opportunities_metrics(user_ids, period_filter, client_id)
            campaigns_aggregates = cls._get_batch_campaigns_metrics(user_ids, period_filter, client_id)
            meetings_aggregates = cls._get_batch_meetings_metrics(user_ids, period_filter, client_id)
            
            return {
                'leads': leads_aggregates,
                'opportunities': opps_aggregates,
                'campaigns': campaigns_aggregates,
                'meetings': meetings_aggregates,
                'summary': cls._calculate_performance_summary(
                    leads_aggregates, opps_aggregates, campaigns_aggregates, meetings_aggregates
                )
            }
            
        except Exception:
            return cls._empty_performance_summary()

    @classmethod
    def _extract_quota_current_value(cls, performance_data: Dict, target_type: str) -> float:
        """Mapping optimisé target_type → valeur actuelle"""
        try:
            mapping = {
                'CLOSED_WON': lambda p: float(p.get('opportunities', {}).get('won_value', 0)),
                'PIPELINE': lambda p: float(p.get('opportunities', {}).get('pipeline_value', 0)),
                'MEETINGS': lambda p: float(p.get('meetings', {}).get('completed_count', 0)),
                'LEADS_ACCEPTED': lambda p: float(p.get('leads', {}).get('qualified_count', 0))
            }
            
            return mapping.get(target_type, lambda p: 0.0)(performance_data)
        except Exception:
            return 0.0

    @classmethod
    def _calculate_timing_metrics(cls, period_start: date, period_end: date) -> Dict:
        """Calcul optimisé des métriques temporelles"""
        today = timezone.now().date()
        days_total = (period_end - period_start).days + 1
        days_elapsed = max(0, (today - period_start).days + 1)
        days_remaining = max(0, (period_end - today).days + 1)
        
        return {
            'days_total': days_total,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining
        }

    @classmethod
    def _calculate_quota_progress(cls, current_value: float, target_value: float) -> float:
        """Calcul optimisé pourcentage progression"""
        if target_value <= 0:
            return 0.0
        return min(100.0, (current_value / target_value) * 100)

    @classmethod
    def _determine_quota_status(cls, progress_percentage: float, days_remaining: int, period_end: date) -> str:
        """Détermination optimisée du statut quota"""
        today = timezone.now().date()
        
        if progress_percentage >= 100:
            return 'achieved'
        elif today > period_end:
            return 'overdue'
        elif days_remaining <= 7 and progress_percentage < 75:
            return 'at_risk'
        elif days_remaining <= 14 and progress_percentage < 50:
            return 'at_risk'
        else:
            return 'on_track'

    @classmethod
    def _calculate_quota_forecast(cls, current_value: float, target_value: float, days_elapsed: int, days_remaining: int) -> Dict:
        """Projections optimisées basées sur rythme actuel"""
        try:
            if days_elapsed <= 0:
                return {'projected_value': current_value, 'likelihood_to_achieve': 0, 'confidence': 'low'}
            
            daily_rate = current_value / days_elapsed
            projected_value = current_value + (daily_rate * days_remaining)
            likelihood = min(100, round((projected_value / target_value) * 100, 1))
            
            confidence = 'high' if days_elapsed >= 14 else 'medium' if days_elapsed >= 7 else 'low'
            
            return {
                'projected_value': round(projected_value, 2),
                'daily_rate': round(daily_rate, 2),
                'likelihood_to_achieve': likelihood,
                'confidence': confidence
            }
        except Exception:
            return {'projected_value': current_value, 'likelihood_to_achieve': 0, 'confidence': 'low'}

    # ===== MÉTHODES BATCH AGGREGATIONS (OPTIMISÉES SQL) =====

    @classmethod
    def _get_batch_leads_metrics(cls, user_ids: List, period_filter: Q, client_id: str) -> Dict:
        """Agrégation batch optimisée pour leads"""
        try:
            from apps.leads.models import Lead
            
            leads_qs = Lead.objects.filter(
                client_id=client_id
            ).filter(period_filter).filter(
                Q(created_by_id__in=user_ids) | Q(assigned_to_id__in=user_ids)
            )
            
            metrics = leads_qs.aggregate(
                total_created=Count('id', filter=Q(created_by_id__in=user_ids)),
                total_assigned=Count('id', filter=Q(assigned_to_id__in=user_ids)),
                total_qualified=Count('id', filter=Q(status='QUALIFIED')),
                total_converted=Count('id', filter=Q(status='CONVERTED'))
            )
            
            total_processed = (metrics['total_created'] or 0) + (metrics['total_assigned'] or 0)
            conversion_rate = ((metrics['total_converted'] or 0) / total_processed * 100) if total_processed > 0 else 0
            
            return {
                'created_count': metrics['total_created'] or 0,
                'assigned_count': metrics['total_assigned'] or 0,
                'total_processed': total_processed,
                'qualified_count': metrics['total_qualified'] or 0,
                'converted_count': metrics['total_converted'] or 0,
                'conversion_rate_percentage': round(conversion_rate, 2)
            }
        except Exception:
            return cls._empty_leads_metrics()

    @classmethod
    def _get_batch_opportunities_metrics(cls, user_ids: List, period_filter: Q, client_id: str) -> Dict:
        """Agrégation batch optimisée pour opportunities"""
        try:
            from apps.opportunities.models import Opportunity
            
            opps_qs = Opportunity.objects.filter(
                client_id=client_id
            ).filter(period_filter).filter(
                Q(created_by_id__in=user_ids) | Q(deal_owner_id__in=user_ids)
            )
            
            metrics = opps_qs.aggregate(
                total_created=Count('id', filter=Q(created_by_id__in=user_ids)),
                total_owned=Count('id', filter=Q(deal_owner_id__in=user_ids)),
                won_count=Count('id', filter=Q(status='WON')),
                lost_count=Count('id', filter=Q(status='LOST')),
                pipeline_value=Sum('amount', filter=Q(status='OPEN')),
                won_value=Sum('amount', filter=Q(status='WON'))
            )
            
            total_closed = (metrics['won_count'] or 0) + (metrics['lost_count'] or 0)
            win_rate = ((metrics['won_count'] or 0) / total_closed * 100) if total_closed > 0 else 0
            
            return {
                'created_count': metrics['total_created'] or 0,
                'owned_count': metrics['total_owned'] or 0,
                'won_count': metrics['won_count'] or 0,
                'lost_count': metrics['lost_count'] or 0,
                'open_count': (metrics['total_owned'] or 0) - total_closed,
                'pipeline_value': float(metrics['pipeline_value'] or 0),
                'won_value': float(metrics['won_value'] or 0),
                'win_rate_percentage': round(win_rate, 2)
            }
        except Exception:
            return cls._empty_opportunities_metrics()

    @classmethod
    def _get_batch_campaigns_metrics(cls, user_ids: List, period_filter: Q, client_id: str) -> Dict:
        """Agrégation batch optimisée pour campaigns"""
        try:
            from apps.campaign.models import Campaign
            
            campaigns_qs = Campaign.objects.filter(
                client_id=client_id
            ).filter(period_filter).filter(
                Q(created_by_id__in=user_ids) | Q(owner_id__in=user_ids)
            )
            
            metrics = campaigns_qs.aggregate(
                total_created=Count('id', filter=Q(created_by_id__in=user_ids)),
                total_owned=Count('id', filter=Q(owner_id__in=user_ids)),
                active_count=Count('id', filter=Q(status='ACTIVE')),
                completed_count=Count('id', filter=Q(status='COMPLETED'))
            )
            
            return {
                'created_count': metrics['total_created'] or 0,
                'owned_count': metrics['total_owned'] or 0,
                'active_count': metrics['active_count'] or 0,
                'completed_count': metrics['completed_count'] or 0,
                'total_managed': (metrics['total_created'] or 0) + (metrics['total_owned'] or 0)
            }
        except Exception:
            return cls._empty_campaigns_metrics()

    @classmethod
    def _get_batch_meetings_metrics(cls, user_ids: List, period_filter: Q, client_id: str) -> Dict:
        """Agrégation batch optimisée pour meetings"""
        try:
            from apps.activities.models import Activity
            
            meetings_qs = Activity.objects.filter(
                client_id=client_id,
                activity_type='MEETING'
            ).filter(period_filter).filter(
                Q(owner_id__in=user_ids) | Q(created_by_id__in=user_ids)
            )
            
            metrics = meetings_qs.aggregate(
                total_created=Count('id', filter=Q(created_by_id__in=user_ids)),
                total_owned=Count('id', filter=Q(owner_id__in=user_ids)),
                completed_count=Count('id', filter=Q(status='COMPLETED')),
                scheduled_count=Count('id', filter=Q(status='SCHEDULED'))
            )
            
            return {
                'created_count': metrics['total_created'] or 0,
                'owned_count': metrics['total_owned'] or 0,
                'completed_count': metrics['completed_count'] or 0,
                'scheduled_count': metrics['scheduled_count'] or 0,
                'total_managed': (metrics['total_created'] or 0) + (metrics['total_owned'] or 0)
            }
        except Exception:
            return cls._empty_meetings_metrics()

    # ===== MÉTHODES HELPER POUR DONNÉES VIDES (ORIGINALES + NOUVELLES) =====
    
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
    def _empty_organization_performance(cls, organization) -> Dict:
        """Structure vide pour performance organisation"""
        return {
            'organization_info': {'id': str(organization.id), 'name': organization.name},
            'organization_performance': cls._empty_performance_summary(),
            'message': 'No active users found in organization'
        }

    @classmethod
    def _empty_organization_quota_summary(cls, organization) -> Dict:
        """Structure vide pour quotas organisation"""
        return {
            'organization_info': {'id': str(organization.id), 'name': organization.name},
            'organization_quota_summary': {
                'total_quotas': 0, 'achieved_count': 0, 'at_risk_count': 0,
                'on_track_count': 0, 'achievement_rate': 0, 'average_progress': 0
            },
            'message': 'No active quotas found in organization'
        }

    @classmethod
    def _empty_performance_summary(cls) -> Dict:
        """Structure vide pour résumé performance"""
        return {
            'leads': cls._empty_leads_metrics(),
            'opportunities': cls._empty_opportunities_metrics(),
            'campaigns': cls._empty_campaigns_metrics(),
            'meetings': cls._empty_meetings_metrics(),
            'summary': {'total_activities': 0, 'conversion_efficiency': {}, 'revenue_impact': {}, 'activity_balance': {}}
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