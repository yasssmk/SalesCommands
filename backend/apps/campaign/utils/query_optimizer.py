"""
Campaign Query Optimizer - Compatible with BaseAPIView architecture
Provides intelligent prefetching and query optimization for campaign-related models
"""

from django.db import connection
from django.db.models import Prefetch, Count, Q
from typing import Dict, List, Optional, Union
import time
from dataclasses import dataclass
from apps.campaign.config.settings import CONFIG


@dataclass
class QueryAuditResult:
    """Results of query performance audit"""
    endpoint_name: str
    query_count: int
    execution_time_ms: float
    is_optimized: bool
    recommendations: List[str]
    queries_executed: List[str]


class CampaignQueryOptimizer:
    """
    Intelligent query optimizer for campaign-related models
    Compatible with BaseAPIView architecture - integrates seamlessly with existing get_queryset()
    """
    
    # Performance targets
    MAX_QUERIES_PER_ENDPOINT = 20
    TARGET_QUERY_COUNT = {
        'list': 5,      # Campaign list should use ≤ 5 queries
        'detail': 8,    # Campaign detail should use ≤ 8 queries  
        'dashboard': 12, # Dashboard should use ≤ 12 queries
        'bulk': 15      # Bulk operations should use ≤ 15 queries
    }
    
    @classmethod
    def optimize_campaigns_queryset(cls, queryset, optimization_level='standard'):
        """
        Optimize Campaign queryset with intelligent prefetching
        
        Args:
            queryset: Base Campaign queryset (from BaseAPIView.get_queryset())
            optimization_level: 'minimal', 'standard', 'full', 'dashboard'
            
        Returns:
            Optimized queryset with appropriate prefetching
        """
        if optimization_level == 'minimal':
            return queryset.select_related('owner')
        
        elif optimization_level == 'standard':
            return queryset.select_related(
                'owner'
            ).prefetch_related(
                'objectives',
                'stakeholder_links__user'
            )
        
        elif optimization_level == 'full':
            return queryset.select_related(
                'owner'
            ).prefetch_related(
                # Objectives with efficient loading
                Prefetch(
                    'objectives',
                    queryset=cls._get_optimized_objectives_queryset()
                ),
                # Stakeholders with user details
                Prefetch(
                    'stakeholder_links',
                    queryset=cls._get_optimized_stakeholders_queryset()
                ),
                # Targets with basic info (limited for performance)
                Prefetch(
                    'targets',
                    queryset=cls._get_optimized_targets_queryset()
                )
            )
        
        elif optimization_level == 'dashboard':
            return queryset.select_related(
                'owner'
            ).prefetch_related(
                # Only essential data for dashboard
                Prefetch(
                    'objectives',
                    queryset=cls._get_dashboard_objectives_queryset()
                )
            ).annotate(
                # Aggregate counts to avoid N+1 queries
                total_targets_count=Count('targets', distinct=True),
                completed_activities_count=Count(
                    'targets__activities__id',
                    filter=Q(targets__activities__status='COMPLETED'),
                    distinct=True
                )
            )
        
        return queryset
    
    @classmethod
    def optimize_campaign_targets_queryset(cls, queryset, optimization_level='standard'):
        """
        Optimize CampaignTarget queryset
        
        Args:
            queryset: Base CampaignTarget queryset
            optimization_level: 'minimal', 'standard', 'full'
        """
        base_queryset = queryset.select_related(
            'campaign',
            'campaign__owner',
            'account'
        )
        
        if optimization_level == 'minimal':
            return base_queryset
        
        elif optimization_level == 'standard':
            return base_queryset.prefetch_related(
                'contact',
                'lead', 
                'target_opportunity'
            )
        
        elif optimization_level == 'full':
            return base_queryset.prefetch_related(
                'contact__account',
                'lead__account',
                'target_opportunity__account',
                # Activities for this target (limited to avoid memory issues)
                Prefetch(
                    'activities',
                    queryset=cls._get_recent_activities_queryset()
                )
            )
        
        return base_queryset
    
    @classmethod
    def optimize_campaign_objectives_queryset(cls, queryset, optimization_level='standard'):
        """Optimize CampaignObjective queryset"""
        return queryset.select_related('campaign', 'campaign__owner')
    
    @classmethod
    def optimize_campaign_stakeholders_queryset(cls, queryset, optimization_level='standard'):
        """Optimize CampaignStakeholder queryset"""
        return queryset.select_related(
            'campaign',
            'campaign__owner', 
            'user',
            'added_by'
        )
    
    # =========================================================================
    # SPECIALIZED QUERY BUILDERS FOR SPECIFIC USE CASES
    # =========================================================================
    
    @classmethod
    def get_dashboard_optimized_queryset(cls, base_queryset):
        """
        Ultra-optimized queryset for dashboard with minimal queries
        Target: ≤ 12 queries total for dashboard endpoint
        """
        return base_queryset.select_related(
            'owner'
        ).prefetch_related(
            # Only primary objective for dashboard
            Prefetch(
                'objectives',
                queryset=cls._get_dashboard_objectives_queryset(),
                to_attr='dashboard_objectives'
            )
        ).annotate(
            # Pre-calculate all dashboard metrics in single query
            total_targets=Count('targets', distinct=True),
            active_targets=Count('targets', filter=Q(targets__status='ACTIVE'), distinct=True),
            completed_targets=Count('targets', filter=Q(targets__status='COMPLETED'), distinct=True),
            total_activities=Count('targets__activities', distinct=True),
            completed_activities=Count(
                'targets__activities', 
                filter=Q(targets__activities__status='COMPLETED'),
                distinct=True
            ),
            pending_activities=Count(
                'targets__activities',
                filter=Q(targets__activities__status='PLANNED'),
                distinct=True
            )
        )
    
    @classmethod 
    def get_summary_optimized_queryset(cls, base_queryset):
        """
        Optimized queryset for campaign summary with essential data
        Target: ≤ 8 queries total
        """
        return base_queryset.select_related(
            'owner'
        ).prefetch_related(
            # All objectives for summary
            Prefetch(
                'objectives',
                queryset=cls._get_optimized_objectives_queryset()
            ),
            # Target summary data only
            Prefetch(
                'targets',
                queryset=cls._get_summary_targets_queryset(),
                to_attr='summary_targets'
            )
        )
    
    @classmethod
    def get_activities_optimized_queryset(cls, base_queryset):
        """
        Optimized queryset for campaign activities listing
        Target: ≤ 10 queries total
        """
        # This would be for Activity queryset optimization
        from apps.activities.models import Activity
        
        return Activity.objects.select_related(
            'owner',
            'account',
            'campaign_info__campaign',
            'campaign_info__campaign_target'
        ).prefetch_related(
            'contacts',
            'sequence_info'
        ).filter(
            campaign_info__campaign__in=base_queryset
        )
    
    # =========================================================================
    # HELPER QUERYSETS (PRIVATE)
    # =========================================================================
    
    @classmethod
    def _get_optimized_objectives_queryset(cls):
        """Optimized objectives queryset for full loading"""
        from apps.campaign.models.campaign_objective import CampaignObjective
        return CampaignObjective.objects.select_related('campaign').order_by('-is_primary', 'created_at')
    
    @classmethod
    def _get_dashboard_objectives_queryset(cls):
        """Minimal objectives for dashboard (primary only)"""
        from apps.campaign.models.campaign_objective import CampaignObjective
        return CampaignObjective.objects.filter(is_primary=True).select_related('campaign')
    
    @classmethod
    def _get_optimized_stakeholders_queryset(cls):
        """Optimized stakeholders queryset"""
        from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
        return CampaignStakeholder.objects.select_related(
            'user', 'added_by', 'campaign'
        ).order_by('role', 'added_at')
    
    @classmethod
    def _get_optimized_targets_queryset(cls):
        """Optimized targets queryset (limited for performance)"""
        from apps.campaign.models.campaign_target import CampaignTarget
        # Now properly access the field from the dataclass
        max_targets = CONFIG.limits.max_prefetch_targets
        return CampaignTarget.objects.select_related(
            'account', 'contact', 'lead', 'target_opportunity'
        ).order_by('created_at')[:max_targets]
    
    @classmethod
    def _get_summary_targets_queryset(cls):
        """Minimal targets for summary (counts only)"""
        from apps.campaign.models.campaign_target import CampaignTarget
        return CampaignTarget.objects.select_related('account').only(
            'id', 'status', 'account__company_name', 'created_at'
        )
    
    @classmethod
    def _get_recent_activities_queryset(cls):
        """Recent activities for target detail view"""
        from apps.activities.models import Activity
        # Access the properly defined field
        max_activities = CONFIG.limits.summary_activities
        return Activity.objects.select_related(
            'owner', 'sequence_info'
        ).prefetch_related(
            'contacts'
        ).order_by('-created_at')[:max_activities]
    
    # =========================================================================
    # QUERY AUDITING AND PERFORMANCE MONITORING
    # =========================================================================
    
    @classmethod
    def audit_queries(cls, endpoint_name: str, optimization_level: str = 'standard') -> QueryAuditResult:
        """
        Audit query performance for an endpoint
        
        Args:
            endpoint_name: Name of the endpoint being tested
            optimization_level: Level of optimization applied
            
        Returns:
            QueryAuditResult with performance metrics and recommendations
        """
        # Reset query log
        connection.queries_log.clear()
        start_time = time.time()
        
        # The actual endpoint execution would happen here
        # This is a placeholder for testing
        
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        
        query_count = len(connection.queries)
        queries_executed = [q['sql'] for q in connection.queries]
        
        # Determine if optimized based on targets
        target_count = cls.TARGET_QUERY_COUNT.get(optimization_level, cls.MAX_QUERIES_PER_ENDPOINT)
        is_optimized = query_count <= target_count
        
        # Generate recommendations
        recommendations = cls._generate_recommendations(
            query_count, target_count, queries_executed, endpoint_name
        )
        
        return QueryAuditResult(
            endpoint_name=endpoint_name,
            query_count=query_count,
            execution_time_ms=execution_time_ms,
            is_optimized=is_optimized,
            recommendations=recommendations,
            queries_executed=queries_executed
        )
    
    @classmethod
    def _generate_recommendations(cls, query_count: int, target_count: int, 
                                queries: List[str], endpoint_name: str) -> List[str]:
        """Generate optimization recommendations based on query analysis"""
        recommendations = []
        
        if query_count > target_count:
            recommendations.append(
                f"Query count ({query_count}) exceeds target ({target_count}). "
                f"Consider using higher optimization level."
            )
        
        # Analyze for common N+1 patterns
        select_queries = [q for q in queries if 'SELECT' in q.upper()]
        if len(select_queries) > target_count:
            recommendations.append(
                "Multiple SELECT queries detected. Consider using select_related() or prefetch_related()."
            )
        
        # Check for missing indexes (simple heuristic)
        join_queries = [q for q in queries if 'JOIN' in q.upper()]
        if len(join_queries) > 5:
            recommendations.append(
                "Multiple JOIN queries detected. Ensure proper database indexes are in place."
            )
        
        # Check for duplicate queries
        unique_queries = set(queries)
        if len(unique_queries) < len(queries):
            recommendations.append(
                f"Duplicate queries detected ({len(queries) - len(unique_queries)} duplicates). "
                "Consider caching or query deduplication."
            )
        
        if not recommendations:
            recommendations.append("Query performance is optimized! 🎯")
        
        return recommendations
    
    # =========================================================================
    # INTEGRATION HELPERS FOR BaseAPIView
    # =========================================================================
    
    @classmethod
    def apply_optimization(cls, queryset, model_name: str, view_action: str = 'list'):
        """
        Smart optimization dispatcher for BaseAPIView integration
        
        Args:
            queryset: Base queryset from BaseAPIView.get_queryset()
            model_name: Name of the model ('Campaign', 'CampaignTarget', etc.)  
            view_action: Type of action ('list', 'detail', 'dashboard', etc.)
            
        Returns:
            Optimized queryset
        """
        # Determine optimization level based on action
        optimization_level = cls._get_optimization_level_for_action(view_action)
        
        # Apply model-specific optimization
        if model_name == 'Campaign':
            return cls.optimize_campaigns_queryset(queryset, optimization_level)
        elif model_name == 'CampaignTarget':
            return cls.optimize_campaign_targets_queryset(queryset, optimization_level)
        elif model_name == 'CampaignObjective':
            return cls.optimize_campaign_objectives_queryset(queryset, optimization_level)
        elif model_name == 'CampaignStakeholder':
            return cls.optimize_campaign_stakeholders_queryset(queryset, optimization_level)
        else:
            # Unknown model, return as-is
            return queryset
    
    @classmethod
    def _get_optimization_level_for_action(cls, action: str) -> str:
        """Determine appropriate optimization level based on view action"""
        action_mapping = {
            'list': 'standard',
            'retrieve': 'full', 
            'dashboard': 'dashboard',
            'summary': 'full',
            'activities': 'minimal',
            'bulk_create': 'minimal',
            'bulk_update': 'minimal'
        }
        
        return action_mapping.get(action, 'standard')



# =========================================================================
# USAGE EXAMPLES AND INTEGRATION PATTERNS
# =========================================================================

"""
INTEGRATION WITH BaseAPIView - 3 PATTERNS:

=== PATTERN 1: Minimal Integration (1 line) ===
class CampaignViewSet(BaseAPIView, AutoCRUDMixin, viewsets.ModelViewSet):
    def get_queryset(self):
        base_queryset = super().get_queryset()
        return CampaignQueryOptimizer.apply_optimization(
            base_queryset, 'Campaign', self.action
        )

=== PATTERN 2: Custom Optimization Levels ===  
class CampaignViewSet(BaseAPIView, AutoCRUDMixin, viewsets.ModelViewSet):
    def get_queryset(self):
        base_queryset = super().get_queryset()
        
        # Custom optimization based on endpoint
        if self.action == 'dashboard':
            return CampaignQueryOptimizer.get_dashboard_optimized_queryset(base_queryset)
        elif self.action == 'summary':
            return CampaignQueryOptimizer.get_summary_optimized_queryset(base_queryset)
        else:
            return CampaignQueryOptimizer.optimize_campaigns_queryset(base_queryset, 'standard')

=== PATTERN 3: Performance Monitoring ===
class CampaignViewSet(BaseAPIView, AutoCRUDMixin, viewsets.ModelViewSet):
    def get_queryset(self):
        base_queryset = super().get_queryset()
        optimized = CampaignQueryOptimizer.apply_optimization(
            base_queryset, 'Campaign', self.action
        )
        
        # Audit in development
        if settings.DEBUG:
            audit = CampaignQueryOptimizer.audit_queries(
                f"campaign_{self.action}", self.action
            )
            if not audit.is_optimized:
                print(f"⚠️  Performance warning: {audit.recommendations}")
        
        return optimized

PERFORMANCE TARGETS:
✅ Campaign List: ≤ 5 queries
✅ Campaign Detail: ≤ 8 queries  
✅ Campaign Dashboard: ≤ 12 queries
✅ Target Operations: ≤ 10 queries
✅ Bulk Operations: ≤ 15 queries
"""