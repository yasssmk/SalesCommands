// frontend/src/sections/accounts/decision-cycles/DecisionStepOverviewTab.jsx

'use client';

import { useState, useCallback } from 'react';
import PropTypes from 'prop-types';

// MUI
import { useTheme, alpha } from '@mui/material/styles';
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
import ContactsOutlined from '@ant-design/icons/ContactsOutlined';

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

// Project imports - Shared hook
import { useDecisionStepEdit } from 'hooks/useDecisionStepEdit';

// Project imports - Permissions
import { useUserPermissions, canViewManagerNotes, canEditManagerNotes } from 'hooks/useUserPermissions';

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
export default function DecisionStepOverviewTab({ step, account, onUpdate }) {
  const theme = useTheme();
  
  // Derive accountId
  const accountId = account?.id || step?.account_id;
  
  // ==============================|| SHARED EDIT HOOK ||============================== //
  
  const {
    saving,
    handleSaveField,
    handleSaveMultiSelect,
    handleStatusChange,
    handleExpectedEndChange,
    handleSaveManagerNotes,
    handleDeleteManagerNotes,
    departmentOptions,
    contactOptions,
    deptLoading,
    contactsLoading
  } = useDecisionStepEdit({ step, accountId, onUpdate });
  
  // ==============================|| STALLED ACTION STATE ||============================== //
  
  // Activity Modal for stalled actions
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityModalType, setActivityModalType] = useState(null);
  
  // User permissions for manager notes
  const { currentUserId, isAdmin, isManager } = useUserPermissions();
  
  // ==============================|| STALLED ACTION HANDLERS ||============================== //

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
    return handleStatusChange('VALIDATED');
  }, [handleStatusChange]);

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
  }, [handleActivityModalClose, onUpdate]);

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

            {/* -------------------- ALL STAKEHOLDERS (Read-only, aggregated) -------------------- */}
            {step?.all_contacts && step.all_contacts.length > 0 && (
              <Box>
                <SectionTitle icon={ContactsOutlined} title="All Stakeholders" />
                <Stack spacing={1}>
                  {step.all_contacts.map((contact) => {
                    const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.email || 'Unknown';
                    const sourceColor = contact.source === 'both' 
                      ? 'primary' 
                      : contact.source === 'activity' 
                        ? 'info' 
                        : 'default';
                    const sourceLabel = contact.source === 'both' 
                      ? 'Manual + Activity' 
                      : contact.source === 'activity' 
                        ? 'From Activity' 
                        : 'Manual';

                    return (
                      <Box
                        key={contact.id}
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          py: 0.75,
                          px: 1,
                          borderRadius: 1,
                          bgcolor: 'grey.50',
                          border: '1px solid',
                          borderColor: 'grey.200'
                        }}
                      >
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography variant="body2" fontWeight={500} noWrap>
                            {name}
                          </Typography>
                          {(contact.job_title || contact.department_name) && (
                            <Typography variant="caption" color="text.secondary" noWrap>
                              {[contact.job_title, contact.department_name].filter(Boolean).join(' · ')}
                            </Typography>
                          )}
                        </Box>
                        <Chip
                          label={sourceLabel}
                          size="small"
                          color={sourceColor}
                          variant="outlined"
                          sx={{ 
                            height: 20, 
                            fontSize: '0.65rem', 
                            '& .MuiChip-label': { px: 0.75 },
                            flexShrink: 0
                          }}
                        />
                      </Box>
                    );
                  })}
                </Stack>
                <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5, display: 'block', fontStyle: 'italic' }}>
                  Merged from manual assignments and linked activities
                </Typography>
              </Box>
            )}

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
  onUpdate: PropTypes.func
};
