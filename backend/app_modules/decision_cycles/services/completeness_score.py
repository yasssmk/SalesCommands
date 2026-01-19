# app_modules/decision_cycles/services/completeness_score.py
"""
Completeness Score Service for Decision Steps.

Provides a configurable way to calculate how "complete" a decision step is
based on filled fields. This gamification element encourages users to
enrich step data.
"""

from django.utils.translation import gettext_lazy as _


class CompletenessScoreService:
    """
    Service to calculate completeness score for DecisionStep instances.

    Usage:
        service = CompletenessScoreService()
        score = service.calculate(step_instance)  # Returns 0-100
        details = service.get_details(step_instance)  # Returns breakdown
    """

    # Field weights: higher weight = more important for completeness
    FIELD_WEIGHTS = {
        'name': 10,
        'stage': 10,
        'expected_end': 15,  
        'description': 8,
        'goal': 8,
        'stakeholder': 6,
        'contacts': 15,
        'departments': 10,
        'criterias': 5,
        'metrics': 5,
        'influence_score': 3,
    }

    SPECIAL_CHECKS = {
        'contacts': 'has_m2m',
        'departments': 'has_m2m',
        'criterias': 'has_json_list',
        'metrics': 'has_json_list',
        'influence_score': 'is_positive',
    }

    THRESHOLDS = {
        'excellent': 80,
        'good': 60,
        'fair': 40,
        'poor': 0,
    }

    def __init__(self, field_weights=None, thresholds=None):
        self.field_weights = field_weights or self.FIELD_WEIGHTS.copy()
        self.thresholds = thresholds or self.THRESHOLDS.copy()

    def calculate(self, step):
        """Calculate completeness score (0-100)."""
        if not step:
            return 0

        total_weight = sum(self.field_weights.values())
        earned_weight = 0

        for field, weight in self.field_weights.items():
            if self._is_field_filled(step, field):
                earned_weight += weight

        if total_weight == 0:
            return 0

        return round((earned_weight / total_weight) * 100)

    def get_details(self, step):
        """Get detailed breakdown of completeness score."""
        if not step:
            return {
                'score': 0,
                'category': 'poor',
                'filled_fields': [],
                'missing_fields': list(self.field_weights.keys()),
                'suggestions': []
            }

        filled = []
        missing = []

        for field, weight in self.field_weights.items():
            if self._is_field_filled(step, field):
                filled.append({'field': field, 'weight': weight})
            else:
                missing.append({'field': field, 'weight': weight})

        score = self.calculate(step)
        category = self._get_category(score)
        missing.sort(key=lambda x: x['weight'], reverse=True)
        suggestions = self._generate_suggestions(missing[:3])

        return {
            'score': score,
            'category': category,
            'filled_fields': filled,
            'missing_fields': missing,
            'suggestions': suggestions
        }

    def _is_field_filled(self, step, field):
        check_type = self.SPECIAL_CHECKS.get(field)

        if check_type == 'has_m2m':
            return self._check_m2m(step, field)
        elif check_type == 'has_json_list':
            return self._check_json_list(step, field)
        elif check_type == 'is_positive':
            return self._check_positive(step, field)
        else:
            return self._check_standard(step, field)

    def _check_standard(self, step, field):
        value = getattr(step, field, None)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)

    def _check_m2m(self, step, field):
        try:
            manager = getattr(step, field, None)
            if manager is None:
                return False
            return manager.exists()
        except Exception:
            return False

    def _check_json_list(self, step, field):
        value = getattr(step, field, None)
        if not value:
            return False
        if isinstance(value, list):
            return len(value) > 0
        return False

    def _check_positive(self, step, field):
        value = getattr(step, field, None)
        if value is None:
            return False
        try:
            return int(value) > 0
        except (ValueError, TypeError):
            return False

    def _get_category(self, score):
        if score >= self.thresholds['excellent']:
            return 'excellent'
        elif score >= self.thresholds['good']:
            return 'good'
        elif score >= self.thresholds['fair']:
            return 'fair'
        return 'poor'

    def _generate_suggestions(self, missing_fields):
        """Generate actionable suggestions for missing fields."""
        # NOTE: step_type and scheduled_date removed - scheduling belongs to Activity
        suggestions_map = {
            'contacts': _('Add contacts involved in this step'),
            'expected_end': _('Set the expected end date for this step'),
            'description': _('Add a description of what will happen'),
            'goal': _('Define the goal of this step'),
            'departments': _('Specify which departments are involved'),
            'stakeholder': _('Identify the key stakeholder'),
            'criterias': _('Add evaluation criteria'),
            'metrics': _('Define success metrics'),
        }

        suggestions = []
        for item in missing_fields:
            field = item['field']
            if field in suggestions_map:
                suggestions.append(str(suggestions_map[field]))

        return suggestions