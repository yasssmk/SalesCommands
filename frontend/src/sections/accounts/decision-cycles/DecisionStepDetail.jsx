// frontend/src/sections/accounts/decision-cycles/DecisionStepDetail.jsx
/**
 * Decision Step Detail Component
 * 
 * Full detail view of a decision step with inline editing.
 * All fields are displayed in read-only mode, click to edit each field.
 * 
 * Features:
 * - Read-only view by default
 * - Click-to-edit on each field
 * - Status quick change
 * - Stakeholder, description, goal, criterias, metrics
 * - Expected days and contacts
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';

// icons
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';
import CloseCircleFilled from '@ant-design/icons/CloseCircleFilled';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import AimOutlined from '@ant-design/icons/AimOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';
import UnorderedListOutlined from '@ant-design/icons/UnorderedListOutlined';

// project imports
import EditableField from './EditableField';
import EditableTextArea from './EditableTextArea';
import EditableChipList from './EditableChipList';
import { 
  updateDecisionStep,
  updateDecisionStepStatus,
  DECISION_STAGES,
  DECISION_STEP_STATUSES 
} from 'api/accounts/decisionCycles';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| STATUS CONFIG ||============================== //

const STATUS_CONFIG = {
  NOT_STARTED: { color: 'default', label: 'Not Started' },
  PENDING_CLIENT: { color: 'warning', label: 'Pending Client' },
  IN_PROGRESS: { color: 'info', label: 'In Progress' },
  IN_CHASING: { color: 'secondary', label: 'In Chasing' },
  VALIDATED: { color: 'success', label: 'Validated' },
  REJECTED: { color: 'error', label: 'Rejected' }
};

const STAGE_LABELS = {
  EXPLORATION: 'Exploration',
  CRITERIA_VALIDATION: 'Criteria Validation',
  SOLUTION_CONFIRMATION: 'Solution Confirmation',
  BUSINESS_VALIDATION: 'Business Validation',
  FORMALIZATION: 'Formalization'
};

// ==============================|| SECTION TITLE ||============================== //

function SectionTitle({ icon: Icon, title }) {
  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
      {Icon && <Icon style={{ fontSize: 16, color: '#8c8c8c' }} />}
      <Typography variant="subtitle2" color="text.secondary" fontWeight={600}>
        {title}
      </Typography>
    </Stack>
  );
}

SectionTitle.propTypes = {
  icon: PropTypes.elementType,
  title: PropTypes.string.isRequired
};

// ==============================|| DECISION STEP DETAIL ||============================== //

/**
 * DecisionStepDetail Component
 * 
 * @param {Object} step - Step data
 * @param {Function} closeModal - Close modal callback
 * @param {Function} onUpdate - Callback after successful update
 * @param {Function} onDelete - Callback when delete is requested
 */
export default function DecisionStepDetail({ step, closeModal, onUpdate, onDelete }) {
  const theme = useTheme();
  
  const [saving, setSaving] = useState(false);
  
  // ==============================|| SAVE HANDLER ||============================== //
  
  const handleSaveField = useCallback(async (fieldKey, newValue) => {
    setSaving(true);
    
    try {
      const payload = { [fieldKey]: newValue };
      const result = await updateDecisionStep(step.id, payload, step.cycle);
      
      if (result.success) {
        displaySuccessSnackbar('Step updated successfully');
        onUpdate?.(result.data);
        return true;
      } else {
        displayErrorSnackbar(result.error || 'Failed to update step');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
      return false;
    } finally {
      setSaving(false);
    }
  }, [step.id, step.cycle, onUpdate]);
  
  // ==============================|| STATUS CHANGE HANDLER ||============================== //
  
  const handleStatusChange = useCallback(async (newStatus) => {
    setSaving(true);
    
    try {
      const result = await updateDecisionStepStatus(step.id, newStatus, step.cycle);
      
      if (result.success) {
        displaySuccessSnackbar('Status updated successfully');
        onUpdate?.(result.data);
        return true;
      } else {
        displayErrorSnackbar(result.error || 'Failed to update status');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
      return false;
    } finally {
      setSaving(false);
    }
  }, [step.id, step.cycle, onUpdate]);
  
  // ==============================|| DELETE HANDLER ||============================== //
  
  const handleDeleteClick = () => {
    onDelete?.(step);
  };

  // ==============================|| RENDER ||============================== //

  const statusConfig = STATUS_CONFIG[step.status] || STATUS_CONFIG.NOT_STARTED;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ p: 2.5, pb: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Stack spacing={1} sx={{ flex: 1, mr: 2 }}>
            {/* Editable Name */}
            <EditableField
              value={step.name}
              fieldKey="name"
              onSave={handleSaveField}
              typography="h5"
              placeholder="Step name"
              required
            />
            
            {/* Stage Badge */}
            <Chip
              size="small"
              label={STAGE_LABELS[step.stage] || step.stage}
              variant="outlined"
              sx={{ alignSelf: 'flex-start' }}
            />
          </Stack>
          
          {/* Actions */}
          <Stack direction="row" spacing={0.5}>
            <Tooltip title="Delete step">
              <IconButton size="small" color="error" onClick={handleDeleteClick}>
                <DeleteOutlined />
              </IconButton>
            </Tooltip>
            <IconButton size="small" onClick={closeModal}>
              <CloseOutlined />
            </IconButton>
          </Stack>
        </Stack>
      </Box>
      
      <Divider />
      
      {/* Content */}
      <Box sx={{ p: 2.5 }}>
        <Grid container spacing={3}>
          
          {/* Status Section */}
          <Grid item xs={12}>
            <SectionTitle icon={CheckCircleFilled} title="Status" />
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {Object.entries(STATUS_CONFIG).map(([statusKey, config]) => (
                <Chip
                  key={statusKey}
                  label={config.label}
                  color={config.color}
                  variant={step.status === statusKey ? 'filled' : 'outlined'}
                  onClick={() => handleStatusChange(statusKey)}
                  sx={{ 
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    '&:hover': {
                      transform: 'scale(1.05)'
                    }
                  }}
                />
              ))}
            </Stack>
          </Grid>
          
          {/* Stakeholder & Expected Days */}
          <Grid item xs={12} sm={6}>
            <SectionTitle icon={UserOutlined} title="Stakeholder" />
            <EditableField
              value={step.stakeholder}
              fieldKey="stakeholder"
              onSave={handleSaveField}
              placeholder="Who is responsible for this step?"
              emptyText="No stakeholder defined"
            />
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <SectionTitle icon={ClockCircleOutlined} title="Expected Days" />
            <EditableField
              value={step.expected_days}
              fieldKey="expected_days"
              onSave={handleSaveField}
              placeholder="Duration in days"
              emptyText="Not estimated"
              type="number"
              suffix=" days"
            />
          </Grid>
          
          {/* Description */}
          <Grid item xs={12}>
            <SectionTitle icon={FileTextOutlined} title="Description" />
            <EditableTextArea
              value={step.description}
              fieldKey="description"
              onSave={handleSaveField}
              placeholder="What will be done in this step?"
              emptyText="No description"
              minRows={2}
            />
          </Grid>
          
          {/* Goal */}
          <Grid item xs={12}>
            <SectionTitle icon={AimOutlined} title="Goal" />
            <EditableTextArea
              value={step.goal}
              fieldKey="goal"
              onSave={handleSaveField}
              placeholder="What this step aims to achieve?"
              emptyText="No goal defined"
              minRows={2}
            />
          </Grid>
          
          {/* Criterias */}
          <Grid item xs={12} sm={6}>
            <SectionTitle icon={UnorderedListOutlined} title="Criterias" />
            <EditableChipList
              values={step.criterias || []}
              fieldKey="criterias"
              onSave={handleSaveField}
              placeholder="Add criteria..."
              emptyText="No criterias defined"
            />
          </Grid>
          
          {/* Metrics */}
          <Grid item xs={12} sm={6}>
            <SectionTitle icon={UnorderedListOutlined} title="Metrics" />
            <EditableChipList
              values={step.metrics || []}
              fieldKey="metrics"
              onSave={handleSaveField}
              placeholder="Add metric..."
              emptyText="No metrics defined"
            />
          </Grid>
          
          {/* Department */}
          {step.department_name && (
            <Grid item xs={12} sm={6}>
              <SectionTitle title="Department" />
              <Typography variant="body2" color="text.secondary">
                {step.department_name}
              </Typography>
            </Grid>
          )}
          
          {/* Contacts */}
          {step.step_contacts && step.step_contacts.length > 0 && (
            <Grid item xs={12}>
              <SectionTitle icon={UserOutlined} title="Contacts" />
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {step.step_contacts.map((contact) => (
                  <Chip
                    key={contact.id}
                    label={contact.contact_name || contact.contact_email}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Stack>
            </Grid>
          )}
          
        </Grid>
      </Box>
      
      <Divider />
      
      {/* Footer */}
      <Box sx={{ p: 2.5 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="caption" color="text.secondary">
            Created {new Date(step.created_at).toLocaleDateString()}
            {step.updated_at && ` · Updated ${new Date(step.updated_at).toLocaleDateString()}`}
          </Typography>
          <Button onClick={closeModal} color="secondary">
            Close
          </Button>
        </Stack>
      </Box>
    </Box>
  );
}

DecisionStepDetail.propTypes = {
  step: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    stage: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    cycle: PropTypes.string,
    stakeholder: PropTypes.string,
    description: PropTypes.string,
    goal: PropTypes.string,
    expected_days: PropTypes.number,
    department_name: PropTypes.string,
    criterias: PropTypes.array,
    metrics: PropTypes.array,
    step_contacts: PropTypes.array,
    created_at: PropTypes.string,
    updated_at: PropTypes.string
  }).isRequired,
  closeModal: PropTypes.func.isRequired,
  onUpdate: PropTypes.func,
  onDelete: PropTypes.func
};