// frontend/src/sections/accounts/decision-cycles/DecisionStepOverviewTab.jsx

'use client';

import { useState, useCallback } from 'react';
import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';

// Date pickers
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';

// Icons
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import HistoryOutlined from '@ant-design/icons/HistoryOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';
import AimOutlined from '@ant-design/icons/AimOutlined';
import UnorderedListOutlined from '@ant-design/icons/UnorderedListOutlined';

// Project imports - Existing editable components
import EditableField from '../EditableField';
import EditableTextArea from '../EditableTextArea';
import EditableChipList from '../EditableChipList';
import EditableMultiSelect from '../EditableMultiSelect';

// Project imports - Stalled Warning
import StalledWarning from 'components/stalled/StalledWarning';

// Project imports - Activity Modal (for stalled actions)
import ActivityModal from 'sections/accounts/activities/ActivityModal';

// Project imports - Phase 2.1 components
import CompletenessScoreWidget from '../CompletenessScoreWidget';
import ManagerNotesSection from '../ManagerNotesSection';

// Project imports - API & hooks
import { 
  updateDecisionStep,
  updateDecisionStepStatus 
} from 'api/accounts/decisionCycles';
import { useGetContactChoices, useGetContacts } from 'api/businessData/contacts';
import { useUserPermissions, canViewManagerNotes, canEditManagerNotes } from 'hooks/useUserPermissions';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| CONFIGURATION ||============================== //

const STATUS_CONFIG = {
  NOT_STARTED: { color: 'default', label: 'Not Started' },
  PENDING_CLIENT: { color: 'warning', label: 'Pending Client' },
  IN_PROGRESS: { color: 'info', label: 'In Progress' },
  IN_CHASING: { color: 'secondary', label: 'In Chasing' },
  VALIDATED: { color: 'success', label: 'Validated' },
  REJECTED: { color: 'error', label: 'Rejected' },
  ON_HOLD: { color: 'default', label: 'On Hold' },
  CANCELLED: { color: 'default', label: 'Cancelled' }
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

// ==============================|| DECISION STEP OVERVIEW TAB ||============================== //

/**
 * Decision Step Overview Tab
 * 
 * Displays step details with inline editing, completeness score,
 * and manager notes section.
 * 
 * Layout:
 * - Left column: Status, Type, Departments, Contacts, Schedule
 * - Right column: Completeness Score, Manager Notes, Timestamps
 * - Bottom: Stakeholder, Description, Goal, Criterias, Metrics
 */
export default function DecisionStepOverviewTab({ step, account, onSave, onUpdate }) {
  const [saving, setSaving] = useState(false);
  
  // Activity Modal for stalled actions
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityModalType, setActivityModalType] = useState(null);
  
  // User permissions for manager notes
  const { currentUserId, isAdmin, isManager } = useUserPermissions();
  
  // Fetch departments for editing
  const { standardDepartments = [], choicesLoading: deptLoading } = useGetContactChoices();
  
  // Fetch contacts for this account
  const accountId = account?.id || step?.account_id;
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
    const success = await onSave(fieldKey, newValue);
    setSaving(false);
    return success;
  }, [onSave]);

  /**
   * Save multi-select fields (departments, contacts)
   */
  const handleSaveMultiSelect = useCallback(async (fieldKey, newIds) => {
    setSaving(true);
    const success = await onSave(fieldKey, newIds);
    setSaving(false);
    return success;
  }, [onSave]);

  /**
   * Handle expected_end date change
   */
  const handleExpectedEndChange = useCallback(async (newDate) => {
    if (!newDate) return;
    const formatted = newDate.format('YYYY-MM-DD');
    return handleSaveField('expected_end', formatted);
  }, [handleSaveField]);

  /**
   * Stalled action: Schedule Call
   */
  const handleScheduleCall = useCallback(() => {
    setActivityModalType('CALL');
    setActivityModalOpen(true);
  }, []);

  /**
   * Stalled action: Schedule Meeting
   */
  const handleScheduleMeeting = useCallback(() => {
    setActivityModalType('MEETING');
    setActivityModalOpen(true);
  }, []);

  /**
   * Stalled action: Mark as Validated
   */
  const handleMarkValidated = useCallback(async () => {
    setSaving(true);
    try {
      const result = await updateDecisionStepStatus(step.id, 'VALIDATED', step.cycle);
      if (result.success) {
        displaySuccessSnackbar('Step marked as validated');
        onUpdate?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to update status');
      }
    } catch (error) {
      displayErrorSnackbar('An error occurred');
    } finally {
      setSaving(false);
    }
  }, [step?.id, step?.cycle, onUpdate]);

  /**
   * Activity modal close
   */
  const handleActivityModalClose = useCallback(() => {
    setActivityModalOpen(false);
    setActivityModalType(null);
  }, []);

  /**
   * Activity created successfully
   */
  const handleActivitySuccess = useCallback(() => {
    handleActivityModalClose();
    onUpdate?.();
    displaySuccessSnackbar('Activity created');
  }, [handleActivityModalClose, onUpdate]);

  /**
   * Quick status change
   */
  const handleStatusChange = useCallback(async (newStatus) => {
    setSaving(true);
    
    try {
      const result = await updateDecisionStepStatus(step.id, newStatus, step.cycle);
      
      if (result.success) {
        displaySuccessSnackbar('Status updated');
        onUpdate?.();
        return true;
      } else {
        displayErrorSnackbar(result.error || 'Failed to update status');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar('An error occurred');
      return false;
    } finally {
      setSaving(false);
    }
  }, [step?.id, step?.cycle, onUpdate]);

  /**
   * Save manager notes
   */
  const handleSaveManagerNotes = useCallback(async (newNotes) => {
    return handleSaveField('manager_notes', newNotes);
  }, [handleSaveField]);

  /**
   * Delete manager notes
   */
  const handleDeleteManagerNotes = useCallback(async () => {
    return handleSaveField('manager_notes', '');
  }, [handleSaveField]);

  // ==============================|| PERMISSION CHECKS ||============================== //

  const stepOwnerId = step?.owner_id || step?.owner;
  const canViewNotes = canViewManagerNotes({
    resourceOwnerId: stepOwnerId,
    currentUserId,
    isAdmin,
    isManager
  });
  const canEditNotes = canEditManagerNotes({ isAdmin, isManager });

  // ==============================|| RENDER ||============================== //

  // Completeness score data (from backend or computed)
  const completenessScore = step?.completeness_score || 0;
  const completenessSuggestions = step?.completeness_suggestions || [];

  return (
    <Box>
      {/* ==================== STALLED WARNING ==================== */}
      <StalledWarning
        isStalled={step?.is_stalled}
        stalledReason={step?.stalled_reason}
        stalledDetails={step?.stalled_details}
        onScheduleCall={handleScheduleCall}
        onScheduleMeeting={handleScheduleMeeting}
        onMarkValidated={handleMarkValidated}
        dismissible={true}
      />

      <Grid container spacing={3}>
        
        {/* ==================== LEFT COLUMN ==================== */}
        <Grid item xs={12} md={6}>
          <Stack spacing={3}>
            
            {/* -------------------- STATUS -------------------- */}
            <Box>
              <SectionTitle icon={CheckCircleFilled} title="Status" />
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {Object.entries(STATUS_CONFIG).map(([statusKey, config]) => (
                  <Chip
                    key={statusKey}
                    label={config.label}
                    color={config.color}
                    variant={step?.status === statusKey ? 'filled' : 'outlined'}
                    onClick={() => handleStatusChange(statusKey)}
                    disabled={saving}
                    size="small"
                    sx={{ 
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      '&:hover': { transform: 'scale(1.05)' }
                    }}
                  />
                ))}
              </Stack>
            </Box>

            {/* -------------------- STEP TYPE -------------------- */}
            <Box>
              <SectionTitle icon={AppstoreOutlined} title="Step Type" />
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {Object.entries(STEP_TYPE_CONFIG).map(([typeKey, config]) => (
                  <Chip
                    key={typeKey}
                    label={config.label}
                    color={config.color}
                    size="small"
                    variant={step?.step_type === typeKey ? 'filled' : 'outlined'}
                    onClick={() => handleSaveField('step_type', typeKey)}
                    disabled={saving}
                    sx={{ 
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      '&:hover': { transform: 'scale(1.05)' }
                    }}
                  />
                ))}
              </Stack>
            </Box>

            {/* -------------------- DEPARTMENTS -------------------- */}
            <Box>
              <SectionTitle icon={TeamOutlined} title="Departments" />
              <EditableMultiSelect
                value={step?.departments_list || []}
                options={departmentOptions}
                fieldKey="department_ids"
                onSave={handleSaveMultiSelect}
                getOptionLabel={(opt) => opt?.name || ''}
                placeholder="Select departments..."
                emptyText="No departments"
                loading={deptLoading}
                chipColor="default"
              />
            </Box>

            {/* -------------------- EXPECTED END DATE -------------------- */}
            <Box>
              <SectionTitle icon={CalendarOutlined} title="Expected End Date" />
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  value={step?.expected_end ? dayjs(step.expected_end) : null}
                  onChange={handleExpectedEndChange}
                  slotProps={{
                    textField: {
                      size: 'small',
                      fullWidth: true,
                      placeholder: 'Select expected end date...'
                    }
                  }}
                  minDate={dayjs()}
                />
              </LocalizationProvider>
            </Box>

            {/* -------------------- STAKEHOLDER -------------------- */}
            <Box>
              <SectionTitle icon={UserOutlined} title="Stakeholder" />
              <EditableField
                value={step?.stakeholder}
                fieldKey="stakeholder"
                onSave={handleSaveField}
                placeholder="Who is responsible for this step?"
                emptyText="No stakeholder defined"
              />
            </Box>

          </Stack>
        </Grid>

        {/* ==================== RIGHT COLUMN ==================== */}
        <Grid item xs={12} md={6}>
          <Stack spacing={3}>
            
            {/* -------------------- COMPLETENESS SCORE -------------------- */}
            <CompletenessScoreWidget
              score={completenessScore}
              suggestions={completenessSuggestions}
              variant="full"
              defaultExpanded={false}
            />

            {/* -------------------- MANAGER NOTES -------------------- */}
            {canViewNotes && (
              <ManagerNotesSection
                notes={step?.manager_notes || ''}
                canView={canViewNotes}
                canEdit={canEditNotes}
                onSave={handleSaveManagerNotes}
                onDelete={handleDeleteManagerNotes}
                loading={saving}
              />
            )}

            {/* -------------------- TIMESTAMPS (Read-only) -------------------- */}
            <Box>
              <SectionTitle icon={HistoryOutlined} title="Timeline" />
              <Stack spacing={0.5}>
                {step?.start_date ? (
                  <Typography variant="body2" color="text.secondary">
                    <strong>Start Date:</strong> {new Date(step.start_date).toLocaleDateString()}
                  </Typography>
                ) : (
                  <Typography variant="body2" color="text.disabled" fontStyle="italic">
                    Start date not set
                  </Typography>
                )}
                {step?.expected_end && (
                  <Typography variant="body2" color="text.secondary">
                    <strong>Expected End:</strong> {new Date(step.expected_end).toLocaleDateString()}
                    {new Date(step.expected_end) < new Date() && (
                      <Typography component="span" variant="caption" color="error.main" sx={{ ml: 0.5 }}>
                        (overdue)
                      </Typography>
                    )}
                  </Typography>
                )}
                {step?.completed_at && (
                  <Typography variant="body2" color="text.secondary">
                    <strong>Completed:</strong> {new Date(step.completed_at).toLocaleString()}
                  </Typography>
                )}
              </Stack>
            </Box>

          </Stack>
        </Grid>

        {/* ==================== FULL WIDTH SECTIONS ==================== */}
        <Grid item xs={12}>
          <Divider sx={{ my: 1 }} />
        </Grid>
        
        {/* -------------------- DESCRIPTION -------------------- */}
        <Grid item xs={12}>
          <SectionTitle icon={FileTextOutlined} title="Description" />
          <EditableTextArea
            value={step?.description}
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
            value={step?.goal}
            fieldKey="goal"
            onSave={handleSaveField}
            placeholder="What this step aims to achieve?"
            emptyText="No goal defined"
            minRows={2}
          />
        </Grid>
        
        {/* -------------------- CRITERIAS & METRICS -------------------- */}
        <Grid item xs={12} sm={6}>
          <SectionTitle icon={UnorderedListOutlined} title="Criterias" />
          <EditableChipList
            values={step?.criterias || []}
            fieldKey="criterias"
            onSave={handleSaveField}
            placeholder="Add criteria..."
            emptyText="No criterias defined"
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <SectionTitle icon={UnorderedListOutlined} title="Metrics" />
          <EditableChipList
            values={step?.metrics || []}
            fieldKey="metrics"
            onSave={handleSaveField}
            placeholder="Add metric..."
            emptyText="No metrics defined"
          />
        </Grid>

      </Grid>
      
      {/* Activity Modal for stalled actions */}
      <ActivityModal
        open={activityModalOpen}
        onClose={handleActivityModalClose}
        activity={null}
        accountId={account?.id || step?.account_id}
        decisionStepId={step?.id}
        decisionCycleId={step?.cycle}
        defaultActivityType={activityModalType}
        onSuccess={handleActivitySuccess}
      />

    </Box>
  );
}

DecisionStepOverviewTab.propTypes = {
  step: PropTypes.object.isRequired,
  account: PropTypes.object,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};
