# app_modules/decision_cycles/services/next_step_draft.py
"""
Next Step Draft Service.

Creates draft data for a next DecisionStep based on a current step.
Used after Activity completion when user confirms "prospect validated next step".

Important:
    - Draft does NOT create the step, only returns data for frontend to display
    - Actual creation uses DecisionStepCreateSerializer with create_activity=False
      to avoid duplicate activity creation
"""

from ..constants import DecisionStage, DecisionStepStatus, DecisionStepType


class NextStepDraftService:
    """
    Service to generate next step draft data.

    Usage:
        service = NextStepDraftService()
        draft = service.create_draft(current_step)
    """

    STAGE_ORDER = [
        DecisionStage.EXPLORATION,
        DecisionStage.CRITERIA_VALIDATION,
        DecisionStage.SOLUTION_CONFIRMATION,
        DecisionStage.BUSINESS_VALIDATION,
        DecisionStage.FORMALIZATION,
    ]

    def create_draft(self, current_step, include_contacts=True, include_departments=True):
        """
        Generate draft data for next step based on current step.

        Args:
            current_step: DecisionStep instance that was just validated
            include_contacts: Whether to copy contact IDs
            include_departments: Whether to copy department IDs

        Returns:
            dict: Draft data for creating next step
        """
        if not current_step:
            return None

        draft = {
            'cycle_id': str(current_step.cycle_id),
            'previous_step_id': str(current_step.id),
            'stage': self._suggest_next_stage(current_step.stage),
            'status': DecisionStepStatus.NOT_STARTED,
            'step_type': DecisionStepType.MEETING,
            'create_activity': False,
            '_draft_metadata': {
                'based_on_step_id': str(current_step.id),
                'based_on_step_name': current_step.name,
                'suggested_stage_display': self._get_stage_display(
                    self._suggest_next_stage(current_step.stage)
                ),
            }
        }

        if include_contacts:
            contact_ids = list(current_step.contacts.values_list('id', flat=True))
            draft['contact_ids'] = [str(cid) for cid in contact_ids]

        if include_departments:
            department_ids = list(
                current_step.step_departments.values_list('department_id', flat=True)
            )
            draft['department_ids'] = [str(did) for did in department_ids]

        return draft

    def _suggest_next_stage(self, current_stage):
        """Suggest the next stage based on current stage."""
        return current_stage

    def _get_stage_display(self, stage):
        """Get human-readable stage name."""
        stage_map = dict(DecisionStage.choices)
        return stage_map.get(stage, stage)

    def get_stage_choices(self, current_stage):
        """Get available stage choices for next step."""
        choices = []
        found_current = False

        for stage in self.STAGE_ORDER:
            if stage == current_stage:
                found_current = True
            if found_current:
                choices.append({
                    'value': stage,
                    'label': self._get_stage_display(stage),
                    'is_current': stage == current_stage,
                    'is_next': stage == self._get_next_stage(current_stage)
                })

        return choices

    def _get_next_stage(self, current_stage):
        """Get the next stage in the progression."""
        try:
            idx = self.STAGE_ORDER.index(current_stage)
            if idx < len(self.STAGE_ORDER) - 1:
                return self.STAGE_ORDER[idx + 1]
        except ValueError:
            pass
        return current_stage
