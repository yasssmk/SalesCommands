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
 * - Status and Step Type quick change
 * - Editable departments and contacts (M2M)
 * - Editable scheduled date/time
 * - Auto-tracked timestamps (started_at, completed_at)
 * - Stakeholder, description, goal, criterias, metrics
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
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import AimOutlined from '@ant-design/icons/AimOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';
import UnorderedListOutlined from '@ant-design/icons/UnorderedListOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import HistoryOutlined from '@ant-design/icons/HistoryOutlined';
import AppstoreOutlined from '@ant-design/icons/AppstoreOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import ContactsOutlined from '@ant-design/icons/ContactsOutlined';

// project imports
import EditableField from './EditableField';
import EditableTextArea from './EditableTextArea';
import EditableChipList from './EditableChipList';
import EditableMultiSelect from './EditableMultiSelect';
import EditableDateTime from './EditableDateTime';
import { 
  updateDecisionStep,
  updateDecisionStepStatus,
  DECISION_STEP_STATUSES
} from 'api/accounts/decisionCycles';
import { useGetContactChoices, useGetContacts } from 'api/businessData/contacts';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| CONFIGURATION ||============================== //

const STATUS_CONFIG = {
  NOT_STARTED: { color: 'default', label: 'Not Started' },
  PENDING_CLIENT: { color: 'warning', label: 'Pending Client' },
  IN_PROGRESS: { color: 'info', label: 'In Progress' },
  IN_CHASING: { color: 'secondary', label: 'In Chasing' },
  VALIDATED: { color: 'success', label: 'Validated' },
  REJECTED: { color: 'error', label: 'Rejected' }
};

const STEP_TYPE_CONFIG = {
  MEETING: { color: 'primary', label: 'Meeting' },
  CALL: { color: 'info', label: 'Call' },
  EMAIL: { color: 'default', label: 'Email' },
  TASK_SELLER: { color: 'warning', label: 'Task (Seller)' },
  TASK_BUYER: { color: 'secondary', label: 'Task (Buyer)' },
  INTERNAL_VALIDATION: { color: 'success', label: 'Internal Validation' },
  OTHER: { color: 'default', label: 'Other' }
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
 * @param {string} accountId - Account UUID for fetching contacts
 */
export default function DecisionStepDetail({ step, closeModal, onUpdate, onDelete, accountId }) {
  const theme = useTheme();
  
  const [saving, setSaving] = useState(false);
  
  // ==============================|| DATA FETCHING ||============================== //
  
  // Fetch departments for editing
  const { standardDepartments = [], choicesLoading: deptLoading } = useGetContactChoices();
  
  // Fetch contacts for this account
  const { contacts = [], contactsLoading } = useGetContacts({ 
    pageSize: 100,
    filters: { account: accountId }
  });

  // Transform departments for EditableMultiSelect
  const departmentOptions = standardDepartments.map(d => ({
    id: d.value || d.id,
    name: d.label || d.name || d.display_name
  }));

  // Transform contacts for EditableMultiSelect  
  const contactOptions = contacts.map(c => ({
    id: c.id,
    name: `${c.first_name || ''} ${c.last_name || ''}`.trim() || c.email || 'Unknown'
  }));
  
  // ==============================|| HANDLERS ||============================== //
  
  /**
   * Save a single field
   */
  const handleSaveField = useCallback(async (fieldKey, newValue) => {
    setSaving(true);
    
    try {
      const payload = { [fieldKey]: newValue };
      const result = await updateDecisionStep(step.id, payload, step.cycle);
      
      if (result.success) {
        displaySuccessSnackbar('Step updated');
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

  /**
   * Save multi-select fields (departments, contacts)
   */
  const handleSaveMultiSelect = useCallback(async (fieldKey, newIds) => {
    setSaving(true);
    
    try {
      const payload = { [fieldKey]: newIds };
      const result = await updateDecisionStep(step.id, payload, step.cycle);
      
      if (result.success) {
        displaySuccessSnackbar('Step updated');
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

  /**
   * Save date and time together
   */
  const handleSaveDateTime = useCallback(async (newDate, newTime) => {
    setSaving(true);
    
    try {
      const payload = { 
        scheduled_date: newDate,
        scheduled_time: newTime
      };
      const result = await updateDecisionStep(step.id, payload, step.cycle);
      
      if (result.success) {
        displaySuccessSnackbar('Schedule updated');
        onUpdate?.(result.data);
        return true;
      } else {
        displayErrorSnackbar(result.error || 'Failed to update schedule');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
      return false;
    } finally {
      setSaving(false);
    }
  }, [step.id, step.cycle, onUpdate]);
  
  /**
   * Quick status change
   */
  const handleStatusChange = useCallback(async (newStatus) => {
    setSaving(true);
    
    try {
      const result = await updateDecisionStepStatus(step.id, newStatus, step.cycle);
      
      if (result.success) {
        displaySuccessSnackbar('Status updated');
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
  
  /**
   * Delete step request
   */
  const handleDeleteClick = () => {
    onDelete?.(step);
  };

  // ==============================|| RENDER ||============================== //

  const statusConfig = STATUS_CONFIG[step.status] || STATUS_CONFIG.NOT_STARTED;
  const stepTypeConfig = STEP_TYPE_CONFIG[step.step_type] || STEP_TYPE_CONFIG.OTHER;

  return (
    <Box>
      {/* ==================== HEADER ==================== */}
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
      
      {/* ==================== CONTENT ==================== */}
      <Box sx={{ p: 2.5 }}>
        <Grid container spacing={3}>
          
          {/* -------------------- STATUS -------------------- */}
          <Grid item xs={12}>
            <SectionTitle icon={CheckCircleFilled} title="Status" />
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {Object.entries(STATUS_CONFIG).map(([statusKey, config]) => (
                <Chip
                  key={statusKey}
                  label={config.label}
                  color={config.color}
                  variant={step.status === statusKey ? 'filled' : 'outlined'}
                  onClick={() => handleStatusChange(statusKey)}
                  disabled={saving}
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

          {/* -------------------- STEP TYPE -------------------- */}
          <Grid item xs={12}>
            <SectionTitle icon={AppstoreOutlined} title="Step Type" />
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {Object.entries(STEP_TYPE_CONFIG).map(([typeKey, config]) => (
                <Chip
                  key={typeKey}
                  label={config.label}
                  color={config.color}
                  size="small"
                  variant={step.step_type === typeKey ? 'filled' : 'outlined'}
                  onClick={() => handleSaveField('step_type', typeKey)}
                  disabled={saving}
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

          {/* -------------------- DEPARTMENTS -------------------- */}
          <Grid item xs={12} sm={6}>
            <SectionTitle icon={TeamOutlined} title="Departments" />
            <EditableMultiSelect
              value={step.departments_list || []}
              options={departmentOptions}
              fieldKey="department_ids"
              onSave={handleSaveMultiSelect}
              getOptionLabel={(opt) => opt?.name || ''}
              placeholder="Select departments..."
              emptyText="No departments"
              loading={deptLoading}
              chipColor="default"
            />
          </Grid>

          {/* -------------------- CONTACTS -------------------- */}
          <Grid item xs={12} sm={6}>
            <SectionTitle icon={ContactsOutlined} title="Contacts" />
            <EditableMultiSelect
              value={(step.step_contacts || []).map(sc => ({
                id: sc.contact_id || sc.contact?.id,
                name: sc.contact_name || sc.contact?.full_name || sc.contact_email || 'Unknown'
              }))}
              options={contactOptions}
              fieldKey="contact_ids"
              onSave={handleSaveMultiSelect}
              getOptionLabel={(opt) => opt?.name || ''}
              placeholder="Select contacts..."
              emptyText="No contacts"
              loading={contactsLoading}
              chipColor="primary"
            />
          </Grid>

          {/* -------------------- SCHEDULED DATE & TIME -------------------- */}
          <Grid item xs={12} sm={6}>
            <SectionTitle icon={CalendarOutlined} title="Scheduled Date & Time" />
            <EditableDateTime
              dateValue={step.scheduled_date}
              timeValue={step.scheduled_time}
              onSave={handleSaveDateTime}
              emptyText="Click to schedule..."
              showTime={true}
            />
          </Grid>

          {/* -------------------- TIMESTAMPS (Read-only) -------------------- */}
          <Grid item xs={12} sm={6}>
            <SectionTitle icon={HistoryOutlined} title="Activity Timestamps" />
            <Stack spacing={0.5}>
              {step.started_at ? (
                <Typography variant="body2" color="text.secondary">
                  <strong>Started:</strong> {new Date(step.started_at).toLocaleString()}
                </Typography>
              ) : (
                <Typography variant="body2" color="text.disabled" fontStyle="italic">
                  Not started yet
                </Typography>
              )}
              {step.completed_at && (
                <Typography variant="body2" color="text.secondary">
                  <strong>Completed:</strong> {new Date(step.completed_at).toLocaleString()}
                </Typography>
              )}
            </Stack>
          </Grid>
          
          {/* -------------------- STAKEHOLDER -------------------- */}
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
          
          {/* -------------------- EXPECTED DAYS -------------------- */}
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
          
          {/* -------------------- DESCRIPTION -------------------- */}
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
          
          {/* -------------------- GOAL -------------------- */}
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
          
          {/* -------------------- CRITERIAS -------------------- */}
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
          
          {/* -------------------- METRICS -------------------- */}
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
          
        </Grid>
      </Box>
      
      <Divider />
      
      {/* ==================== FOOTER ==================== */}
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
    step_type: PropTypes.string,
    cycle: PropTypes.string,
    stakeholder: PropTypes.string,
    description: PropTypes.string,
    goal: PropTypes.string,
    expected_days: PropTypes.number,
    scheduled_date: PropTypes.string,
    scheduled_time: PropTypes.string,
    started_at: PropTypes.string,
    completed_at: PropTypes.string,
    departments_list: PropTypes.array,
    criterias: PropTypes.array,
    metrics: PropTypes.array,
    step_contacts: PropTypes.array,
    created_at: PropTypes.string,
    updated_at: PropTypes.string
  }).isRequired,
  closeModal: PropTypes.func.isRequired,
  onUpdate: PropTypes.func,
  onDelete: PropTypes.func,
  accountId: PropTypes.string
};