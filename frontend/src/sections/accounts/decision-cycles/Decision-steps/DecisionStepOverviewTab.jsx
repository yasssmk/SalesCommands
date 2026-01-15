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

// Icons
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';
import AppstoreOutlined from '@ant-design/icons/AppstoreOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import HistoryOutlined from '@ant-design/icons/HistoryOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';
import AimOutlined from '@ant-design/icons/AimOutlined';
import UnorderedListOutlined from '@ant-design/icons/UnorderedListOutlined';

// Project imports - Existing editable components
import EditableField from '../EditableField';
import EditableTextArea from '../EditableTextArea';
import EditableChipList from '../EditableChipList';
import EditableMultiSelect from '../EditableMultiSelect';
import EditableDateTime from '../EditableDateTime';

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
   * Save date and time together
   */
  const handleSaveDateTime = useCallback(async (newDate, newTime) => {
    setSaving(true);
    
    try {
      const result = await updateDecisionStep(step.id, { 
        scheduled_date: newDate,
        scheduled_time: newTime
      }, step.cycle);
      
      if (result.success) {
        displaySuccessSnackbar('Schedule updated');
        onUpdate?.();
        return true;
      } else {
        displayErrorSnackbar(result.error || 'Failed to update schedule');
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

            {/* -------------------- SCHEDULED DATE & TIME -------------------- */}
            <Box>
              <SectionTitle icon={CalendarOutlined} title="Scheduled Date & Time" />
              <EditableDateTime
                dateValue={step?.scheduled_date}
                timeValue={step?.scheduled_time}
                onSave={handleSaveDateTime}
                emptyText="Click to schedule..."
                showTime={true}
              />
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

            {/* -------------------- EXPECTED DAYS -------------------- */}
            <Box>
              <SectionTitle icon={ClockCircleOutlined} title="Expected Days" />
              <EditableField
                value={step?.expected_days}
                fieldKey="expected_days"
                onSave={handleSaveField}
                placeholder="Duration in days"
                emptyText="Not estimated"
                type="number"
                suffix=" days"
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
              <SectionTitle icon={HistoryOutlined} title="Activity Timestamps" />
              <Stack spacing={0.5}>
                {step?.started_at ? (
                  <Typography variant="body2" color="text.secondary">
                    <strong>Started:</strong> {new Date(step.started_at).toLocaleString()}
                  </Typography>
                ) : (
                  <Typography variant="body2" color="text.disabled" fontStyle="italic">
                    Not started yet
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
    </Box>
  );
}

DecisionStepOverviewTab.propTypes = {
  step: PropTypes.object.isRequired,
  account: PropTypes.object,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};
