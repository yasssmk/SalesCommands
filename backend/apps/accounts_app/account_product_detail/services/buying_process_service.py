# apps/accounts_app/account_product_detail/services/buying_process_service.py

import uuid
from django.db import transaction

class BuyingProcessService:
    """
    Service for managing account-product buying process template data.
    This service only handles the structure of the buying process,
    not the progress tracking (which will be in the Opportunity model).
    """
    
    @classmethod
    def initialize_buying_process(cls, apd, template=None, user=None):
        """
        Initialize a buying process template for an APD.
        
        Args:
            apd: AccountProductDetail instance
            template: Optional template to use for initialization
            user: User performing the action
            
        Returns:
            The updated APD instance
        """
        with transaction.atomic():
            # Start with an empty process or use template if provided
            buying_process = []
            
            if template:
                # Copy template steps
                for idx, step_template in enumerate(template):
                    step_id = f"step_{uuid.uuid4().hex[:8]}"
                    
                    step = {
                        'stepId': step_id,
                        'stepIndex': idx,
                        'prevStepId': None,
                        'nextStepId': None,
                        'stakeholder': step_template.get('stakeholder', ''),
                        'departmentName': step_template.get('departmentName', ''),
                        'stepDescription': step_template.get('stepDescription', ''),
                        'stepGoal': step_template.get('stepGoal', ''),
                        'influenceScore': step_template.get('influenceScore', 0),
                        'criterias': step_template.get('criterias', []),
                        'keyKpis': step_template.get('keyKpis', []),
                        'averageTimeInDays': step_template.get('averageTimeInDays', 0)
                    }
                    
                    buying_process.append(step)
            
            # Set up the linked structure for steps
            for i in range(len(buying_process)):
                # Set previous step ID
                if i > 0:
                    buying_process[i]['prevStepId'] = buying_process[i-1]['stepId']
                else:
                    buying_process[i]['prevStepId'] = None
                
                # Set next step ID
                if i < len(buying_process) - 1:
                    buying_process[i]['nextStepId'] = buying_process[i+1]['stepId']
                else:
                    buying_process[i]['nextStepId'] = None
            
            # Calculate total estimated days
            total_days = sum(step.get('averageTimeInDays', 0) for step in buying_process)
            
            # Update APD with the buying process
            apd.buying_process = buying_process
            if total_days > 0:
                apd.sales_cycle_estimated_days = total_days
            
            # Save the APD
            apd.save(user=user)
            
            return apd
    
    @classmethod
    def add_step(cls, apd, step_data, after_step_id=None, user=None):
        """
        Add a new step to the buying process template.
        
        Args:
            apd: AccountProductDetail instance
            step_data: Data for the new step
            after_step_id: Optional ID of step to add after (default: add at end)
            user: User performing the action
            
        Returns:
            The ID of the newly added step
        """
        with transaction.atomic():
            buying_process = apd.buying_process or []
            
            # Generate unique ID for the new step
            step_id = f"step_{uuid.uuid4().hex[:8]}"
            
            # Create the new step
            new_step = {
                'stepId': step_id,
                'stepIndex': 0,  # Will be recalculated
                'prevStepId': None,
                'nextStepId': None,
                'stakeholder': step_data.get('stakeholder', ''),
                'departmentName': step_data.get('departmentName', ''),
                'stepDescription': step_data.get('stepDescription', ''),
                'stepGoal': step_data.get('stepGoal', ''),
                'influenceScore': step_data.get('influenceScore', 0),
                'criterias': step_data.get('criterias', []),
                'keyKpis': step_data.get('keyKpis', []),
                'averageTimeInDays': step_data.get('averageTimeInDays', 0)
            }
            
            # If after_step_id is provided, insert after that step
            if after_step_id and buying_process:
                reference_step = next((step for step in buying_process if step.get('stepId') == after_step_id), None)
                
                if reference_step:
                    # Get the next step from the reference step
                    next_step_id = reference_step.get('nextStepId')
                    
                    # Update links
                    new_step['prevStepId'] = after_step_id
                    new_step['nextStepId'] = next_step_id
                    reference_step['nextStepId'] = step_id
                    
                    # Update previous link of the next step if it exists
                    if next_step_id:
                        next_step = next((step for step in buying_process if step.get('stepId') == next_step_id), None)
                        if next_step:
                            next_step['prevStepId'] = step_id
                    
                    # Add new step
                    buying_process.append(new_step)
                else:
                    # Reference step not found, add at end
                    cls._add_step_at_end(buying_process, new_step)
            else:
                # No reference step, add at end
                cls._add_step_at_end(buying_process, new_step)
            
            # Recalculate step indices
            cls._recalculate_step_indices(buying_process)
            
            # Update total estimated days
            total_days = sum(step.get('averageTimeInDays', 0) for step in buying_process)
            if total_days > 0:
                apd.sales_cycle_estimated_days = total_days
            
            # Update APD
            apd.buying_process = buying_process
            apd.save(user=user)
            
            return step_id
    
    @classmethod
    def _add_step_at_end(cls, buying_process, new_step):
        """Add a step at the end of the buying process"""
        if buying_process:
            # Get the last step
            last_step = buying_process[-1]
            
            # Update links
            new_step['prevStepId'] = last_step['stepId']
            last_step['nextStepId'] = new_step['stepId']
        
        # Add step to list
        buying_process.append(new_step)
    
    @classmethod
    def _recalculate_step_indices(cls, buying_process):
        """Recalculate step indices to ensure proper sequence"""
        if not buying_process:
            return
        
        # Start with the step that has no previous step (first step)
        first_step = next((step for step in buying_process if not step.get('prevStepId')), None)
        
        if not first_step:
            # No clear first step, just use array order
            for idx, step in enumerate(buying_process):
                step['stepIndex'] = idx
            return
        
        # Follow the linked list structure to assign indices
        current_step = first_step
        idx = 0
        
        while current_step:
            current_step['stepIndex'] = idx
            idx += 1
            
            # Find next step
            next_id = current_step.get('nextStepId')
            if not next_id:
                break
                
            current_step = next((step for step in buying_process if step.get('stepId') == next_id), None)

    @classmethod
    def update_step(cls, apd, step_id, step_data, user=None):
        """
        Update an existing step in the buying process template.
        
        Args:
            apd: AccountProductDetail instance
            step_id: ID of the step to update
            step_data: Updated data for the step
            user: User performing the action
            
        Returns:
            bool: True if successful, False otherwise
        """
        with transaction.atomic():
            buying_process = apd.buying_process or []
            
            # Find the step to update
            step = next((step for step in buying_process if step.get('stepId') == step_id), None)
            
            if not step:
                return False
            
            # Update fields while preserving step structure
            updatable_fields = [
                'stakeholder', 'departmentName', 'stepDescription', 'stepGoal', 
                'influenceScore', 'criterias', 'keyKpis', 'averageTimeInDays'
            ]
            
            for field in updatable_fields:
                if field in step_data:
                    step[field] = step_data[field]
            
            # Update total estimated days
            total_days = sum(step.get('averageTimeInDays', 0) for step in buying_process)
            if total_days > 0:
                apd.sales_cycle_estimated_days = total_days
            
            # Save changes
            apd.buying_process = buying_process
            apd.save(user=user)
            
            return True
    
    @classmethod
    def remove_step(cls, apd, step_id, user=None):
        """
        Remove a step from the buying process template.
        
        Args:
            apd: AccountProductDetail instance
            step_id: ID of the step to remove
            user: User performing the action
            
        Returns:
            bool: True if successful, False otherwise
        """
        with transaction.atomic():
            buying_process = apd.buying_process or []
            
            # Find the step to remove
            step_index = next((i for i, step in enumerate(buying_process) 
                              if step.get('stepId') == step_id), None)
            
            if step_index is None:
                return False
            
            step = buying_process[step_index]
            
            # Update links between adjacent steps
            prev_id = step.get('prevStepId')
            next_id = step.get('nextStepId')
            
            if prev_id:
                prev_step = next((s for s in buying_process if s.get('stepId') == prev_id), None)
                if prev_step:
                    prev_step['nextStepId'] = next_id
            
            if next_id:
                next_step = next((s for s in buying_process if s.get('stepId') == next_id), None)
                if next_step:
                    next_step['prevStepId'] = prev_id
            
            # Remove the step
            buying_process.pop(step_index)
            
            # Recalculate indices
            cls._recalculate_step_indices(buying_process)
            
            # Update total estimated days
            total_days = sum(step.get('averageTimeInDays', 0) for step in buying_process)
            if total_days > 0:
                apd.sales_cycle_estimated_days = total_days
            
            # Save changes
            apd.buying_process = buying_process
            apd.save(user=user)
            
            return True

    @classmethod
    def get_buying_process(cls, apd):
        """
        Get the buying process template with steps in order.
        
        Args:
            apd: AccountProductDetail instance
            
        Returns:
            dict: Buying process data with sorted steps
        """
        buying_process = apd.buying_process or []
        
        if not buying_process:
            return {
                'initialized': False,
                'steps_count': 0,
                'estimated_days': apd.sales_cycle_estimated_days or 0,
                'steps': []
            }
        
        # Sort steps by their index
        sorted_steps = sorted(buying_process, key=lambda x: x.get('stepIndex', 0))
        
        return {
            'initialized': True,
            'steps_count': len(buying_process),
            'estimated_days': apd.sales_cycle_estimated_days or 0,
            'steps': sorted_steps
        }
    
    @classmethod
    def update_from_signal(cls, apd, signal, user=None):
        """
        Update buying process based on a signal.
        
        Args:
            apd: AccountProductDetail instance
            signal: Signal instance containing buying process data
            user: User performing the action
            
        Returns:
            bool: True if process was updated, False otherwise
        """
        with transaction.atomic():
            # Extract step data from signal
            step_data = signal.value
            
            if not isinstance(step_data, dict):
                return False
            
            # Check for required fields
            if not step_data.get('stepDescription') and not step_data.get('stakeholder'):
                return False
            
            # Try to match an existing step
            buying_process = apd.buying_process or []
            
            # Look for matching department or stakeholder
            target_dept = step_data.get('departmentName', '').strip().lower()
            target_stakeholder = step_data.get('stakeholder', '').strip().lower()
            target_desc = step_data.get('stepDescription', '').strip().lower()
            
            # Try to find matching step
            matching_step = None
            
            for step in buying_process:
                step_dept = step.get('departmentName', '').strip().lower()
                step_stakeholder = step.get('stakeholder', '').strip().lower()
                step_desc = step.get('stepDescription', '').strip().lower()
                
                # Match based on department or stakeholder with similar description
                dept_match = target_dept and step_dept and target_dept == step_dept
                stakeholder_match = target_stakeholder and step_stakeholder and target_stakeholder == step_stakeholder
                
                if (dept_match or stakeholder_match):
                    # Found a potential match, check for description similarity
                    if (not target_desc or not step_desc or 
                        target_desc in step_desc or step_desc in target_desc):
                        matching_step = step
                        break
            
            # If we found a match, merge the data
            if matching_step:
                updated = False
                
                # For each field in step_data, update if it has a value
                for field in ['stakeholder', 'departmentName', 'stepDescription', 'stepGoal', 
                              'influenceScore', 'criterias', 'keyKpis', 'averageTimeInDays']:
                    if field in step_data and step_data[field]:
                        # For lists, merge rather than replace
                        if field in ['criterias', 'keyKpis'] and isinstance(step_data[field], list):
                            existing_list = matching_step.get(field, [])
                            if not isinstance(existing_list, list):
                                existing_list = []
                                
                            # Add new items that don't exist
                            for item in step_data[field]:
                                if item not in existing_list:
                                    existing_list.append(item)
                                    updated = True
                            
                            matching_step[field] = existing_list
                        else:
                            # For non-list fields, replace if current value is empty
                            if not matching_step.get(field):
                                matching_step[field] = step_data[field]
                                updated = True
                
                if updated:
                    # Save changes
                    apd.buying_process = buying_process
                    
                    # Update total estimated days
                    total_days = sum(step.get('averageTimeInDays', 0) for step in buying_process)
                    if total_days > 0:
                        apd.sales_cycle_estimated_days = total_days
                        
                    apd.save(user=user)
                
                return updated
            else:
                # No match found, add as a new step
                step_id = cls.add_step(apd, step_data, user=user)
                return bool(step_id)