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
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import ContactsOutlined from '@ant-design/icons/ContactsOutlined';
import ThunderboltOutlined from '@ant-design/icons/ThunderboltOutlined';

// project imports
import EditableField from './EditableField';
import EditableTextArea from './EditableTextArea';
import EditableChipList from './EditableChipList';
import EditableMultiSelect from './EditableMultiSelect';
import EditableDateTime from './EditableDateTime';
import DecisionStepActivities from './DecisionStepActivities';
import { useDecisionStepEdit } from './hooks/useDecisionStepEdit';

// ==============================|| CONFIGURATION ||============================== //

/**
 * Step derived status config.
 * WON/REJECTED/ON_HOLD removed — now cycle-level outcomes.
 * STALLED added — deal dormant, no planned activities.
 */
const STATUS_CONFIG = {
  OVERDUE: { color: 'error', label: 'Overdue' },
  VALIDATED: { color: 'primary', label: 'Validated' },
  IN_PROGRESS: { color: 'secondary', label: 'In Progress' },
  STALLED: { color: 'warning', label: 'Stalled' },
  IN_CHASING: { color: 'warning', label: 'In Chasing' },
  NOT_STARTED: { color: 'default', label: 'Not Started' }
};

/**
 * Pipeline Step Labels (5 fixed steps)
 * IMPLEMENTATION/GO_LIVE removed — pipeline reduced to 5 steps.
 */
const PIPELINE_STEP_LABELS = {
  QUALIFICATION: 'Qualification',
  TECHNICAL_FIT: 'Technical Fit',
  SOLUTION_VALIDATION: 'Solution Validation',
  BUSINESS_CASE: 'Business Case',
  CLOSING: 'Closing'
};

// Legacy alias
const STAGE_LABELS = PIPELINE_STEP_LABELS;

// ==============================|| SECTION TITLE ||============================== //

function SectionTitle({ icon: Icon, title }) {
  const theme = useTheme();

  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
      {Icon && <Icon style={{ fontSize: theme.iconSizes.md, color: theme.palette.text.secondary }} />}
      <Typography variant="subtitle2" color="text.secondary" fontWeight={theme.typography.fontWeightBold}>
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
  
  // ==============================|| SHARED EDIT HOOK ||============================== //
  
const {
    saving,
    handleSaveField,
    handleSaveMultiSelect,
    handleSaveDateTime,
    departmentOptions,
    contactOptions,
    deptLoading,
    contactsLoading
  } = useDecisionStepEdit({ step, accountId, onUpdate });
  
  // ==============================|| MODAL-SPECIFIC HANDLERS ||============================== //
  
  /**
   * Delete step request
   */
  const handleDeleteClick = () => {
    onDelete?.(step);
  };

  // ==============================|| RENDER ||============================== //

  const statusConfig = STATUS_CONFIG[step.derived_status] || STATUS_CONFIG.NOT_STARTED;


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
          
          {/* -------------------- STATUS (read-only, derived from activities) -------------------- */}
          <Grid item xs={12}>
            <SectionTitle icon={CheckCircleFilled} title="Status" />
            <Chip
              label={step.derived_status_display || statusConfig.label}
              color={statusConfig.color}
              size="small"
            />
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
              {step.start_date ? (
                <Typography variant="body2" color="text.secondary">
                  <strong>Started:</strong> {new Date(step.start_date).toLocaleDateString()}
                </Typography>
              ) : (
                <Typography variant="body2" color="text.disabled" fontStyle="italic">
                  Not started yet
                </Typography>
              )}
              {step.expected_end && (
                <Typography variant="body2" color="text.secondary">
                  <strong>Expected End:</strong> {new Date(step.expected_end).toLocaleDateString()}
                  {new Date(step.expected_end) < new Date() && (
                    <Typography component="span" variant="caption" color="error.main" sx={{ ml: 0.5 }}>
                      (overdue)
                    </Typography>
                  )}
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

      {/* ==================== ACTIVITIES SECTION ==================== */}
      <Box sx={{ p: 2.5 }}>
        <SectionTitle icon={ThunderboltOutlined} title="Activities" />
        <DecisionStepActivities 
          stepId={step.id} 
          accountId={accountId}
          cycleId={step.cycle}
        />
      </Box>
      
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
    cycle: PropTypes.string,
    stakeholder: PropTypes.string,
    description: PropTypes.string,
    goal: PropTypes.string,
    expected_end: PropTypes.string,
    start_date: PropTypes.string,
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