from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel
from .client_account import ClientAccount
from django.db.models.expressions import RawSQL


class Team(BaseModel):
    """
    Équipe SANS client scoping pour simplifier
    """
    name = models.CharField(
        max_length=100, 
        help_text=_("Name of the team")
    )

    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='teams',
        help_text=_("Client this team belongs to."),
    )

    # organization = models.ForeignKey(
    #     Organization,
    #     on_delete=models.CASCADE,
    #     related_name='teams',
    #     help_text=_("Organization this team belongs to."),
    # )

    parent_team = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_child_teams',
        help_text=_("Direct parent team in the hierarchy."),
    )

    manager = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_teams',
        help_text=_("Manager of the team."),
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Process Description')
    )

    class Meta:
        db_table = 'teams'
        verbose_name = _('team')
        verbose_name_plural = _('teams')
        unique_together = ('name', 'client_account')
        ordering = ['name']

    def __str__(self):
        """
        Human-readable team representation.
        """
        return f"{self.name} ({self.client_account.name})"
    
    @property
    def client_id(self):
        return self.client_account_id
    
    def get_full_hierarchy(self):
        """
        Return ancestor teams and direct child teams for this team.
        
        This helper is MVP-level and meant for read-only use.
        It does not enforce business rules or validation.
        """
        hierarchy = {
            'parents': [],
            'children': list(self.direct_child_teams.all())
        }

        current = self
        while current.parent_team:
            hierarchy['parents'].append(current.parent_team)
            current = current.parent_team

        return hierarchy
    
    @classmethod
    def get_hierarchical_member_counts(cls, client_id):
        """
        Calculate hierarchical member counts for all teams in a client.
        
        Performance: 2 SQL queries (teams + users), then O(T + U) in-memory processing.
        
        Args:
            client_id: UUID of the client account
            
        Returns:
            dict: Mapping of team_id -> {"total": int, "active": int}
            
        Example:
            Hierarchy: A > B > C
            - C has 3 members (2 active)
            - B has 1 member (1 active)
            - A has 0 direct members
            
            Result:
            {
                'C_uuid': {'total': 3, 'active': 2},
                'B_uuid': {'total': 4, 'active': 3},  # B's 1 + C's 3
                'A_uuid': {'total': 4, 'active': 3},  # A's 0 + B's 4
            }
        """
        from collections import defaultdict
        
        # 1️⃣ Load all teams for this client (1 query)
        teams = list(
            cls.objects.filter(client_account_id=client_id)
            .values('id', 'parent_team_id')
        )
        
        if not teams:
            return {}
        
        # 2️⃣ Load all users with team assignment for this client (1 query)
        from .user import User
        users = list(
            User.objects.filter(
                client_account_id=client_id,
                team_id__isnull=False
            )
            .values('team_id', 'is_active')
        )
        
        # 3️⃣ Build direct member counts per team
        direct_counts = defaultdict(lambda: {'total': 0, 'active': 0})
        
        for user in users:
            team_id = str(user['team_id'])
            direct_counts[team_id]['total'] += 1
            if user['is_active']:
                direct_counts[team_id]['active'] += 1
        
        # 4️⃣ Build parent -> children mapping
        children_map = defaultdict(list)
        all_team_ids = set()
        
        for team in teams:
            team_id = str(team['id'])
            all_team_ids.add(team_id)
            
            if team['parent_team_id']:
                parent_id = str(team['parent_team_id'])
                children_map[parent_id].append(team_id)
        
        # 5️⃣ Calculate hierarchical counts recursively
        hierarchical_counts = {}
        
        def calculate_recursive(team_id):
            """
            Recursively calculate total members for a team and all its descendants.
            Uses memoization to avoid recalculating the same subtrees.
            """
            # If already calculated, return cached result
            if team_id in hierarchical_counts:
                return hierarchical_counts[team_id]
            
            # Start with direct members of this team
            counts = {
                'total': direct_counts[team_id]['total'],
                'active': direct_counts[team_id]['active']
            }
            
            # Add counts from all child teams recursively
            for child_id in children_map[team_id]:
                child_counts = calculate_recursive(child_id)
                counts['total'] += child_counts['total']
                counts['active'] += child_counts['active']
            
            # Cache and return
            hierarchical_counts[team_id] = counts
            return counts
        
        # 6️⃣ Calculate for all teams (starts from roots, memoizes subtrees)
        for team_id in all_team_ids:
            calculate_recursive(team_id)
        
        return hierarchical_counts