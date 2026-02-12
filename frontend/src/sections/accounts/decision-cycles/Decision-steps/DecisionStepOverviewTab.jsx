// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepOverviewTab.jsx
/**
 * Decision Step Overview Tab
 *
 * Dashboard view for a Decision Step workspace.
 *
 * Layout (flat vertical, like ActivityOverviewTab):
 *   SECTION 1: Step Intelligence → Grid md=6|md=6 (Contacts | Users)
 *   SECTION 2: Documentation Readiness → full width (CompletenessScoreWidget, own Card)
 *   SECTION 3: Manager Notes → full width (ManagerNotesSection, own styling)
 *   SECTION 4: Activity Timeline → full width
 *   SECTION 5: Context card (Description, Goal, Criterias, Metrics)
 *
 * All data is read-only (derived from backend) except Context fields.
 * Follows ActivityOverviewTab spacing and theme patterns exactly.
 */

'use client';

import { useMemo } from 'react';
import PropTypes from 'prop-types';

// MUI
import { useTheme, alpha } from '@mui/material/styles';
import AvatarGroup from '@mui/material/AvatarGroup';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import MuiAvatar from '@mui/material/Avatar';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// Icons
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import NodeIndexOutlined from '@ant-design/icons/NodeIndexOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';

// Project imports — Existing editable components
import EditableTextArea from '../EditableTextArea';
import EditableChipList from '../EditableChipList';

// Project imports — Shared widgets (DO NOT recreate)
import CompletenessScoreWidget from '../CompletenessScoreWidget';
import ManagerNotesSection from '../ManagerNotesSection';

// Project imports — Hooks
import { useDecisionStepEdit } from 'hooks/useDecisionStepEdit';
import { useUserPermissions, canViewManagerNotes, canEditManagerNotes } from 'hooks/useUserPermissions';
import { useGetActivitiesByStep } from 'api/accounts/activities';

// ==============================|| SECTION HEADER (matches ActivityOverviewTab) ||============================== //

function SectionHeader({ icon: Icon, title }) {
  const theme = useTheme();

  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
      {Icon && <Icon style={{ fontSize: theme.iconSizes.md, color: theme.palette.text.secondary }} />}
      <Typography variant="subtitle2" fontWeight={theme.typography.fontWeightBold} color="text.primary">
        {title}
      </Typography>
    </Stack>
  );
}

SectionHeader.propTypes = {
  icon: PropTypes.elementType,
  title: PropTypes.string.isRequired
};

// ==============================|| CONTACTS INVOLVED SECTION ||============================== //

/**
 * Shows total contact count + breakdown by department.
 * Data: step.all_contacts (merged manual + activity contacts with department_name).
 */
function ContactsInvolvedSection({ contacts }) {
  const theme = useTheme();

  const allContacts = contacts || [];
  const totalCount = allContacts.length;

  // Group contacts by department_name
  const departmentBreakdown = useMemo(() => {
    const groups = {};
    allContacts.forEach((c) => {
      const dept = c.department_name || 'Other';
      if (!groups[dept]) groups[dept] = 0;
      groups[dept] += 1;
    });
    // Sort by count descending
    return Object.entries(groups).sort((a, b) => b[1] - a[1]);
  }, [allContacts]);

  return (
    <Box>
      <Typography variant="overline" color="text.secondary" gutterBottom display="block">
        Contacts Involved
      </Typography>

      {totalCount === 0 ? (
        <Typography variant="body2" color="text.disabled" fontStyle="italic">
          No contacts linked yet
        </Typography>
      ) : (
        <Stack spacing={1}>
          {/* Total count */}
          <Typography variant="subtitle2" color="text.primary">
            {totalCount} contact{totalCount !== 1 ? 's' : ''}
          </Typography>

          {/* Department breakdown */}
          {departmentBreakdown.map(([dept, count]) => (
            <Stack key={dept} direction="row" spacing={1} alignItems="center">
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  bgcolor: alpha(theme.palette.primary.main, 0.5),
                  flexShrink: 0
                }}
              />
              <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
                {dept}
              </Typography>
              <Typography variant="body2" color="text.primary" fontWeight={500}>
                {count}
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}
    </Box>
  );
}

ContactsInvolvedSection.propTypes = {
  contacts: PropTypes.array
};

// ==============================|| USERS INVOLVED SECTION ||============================== //

/**
 * Shows AvatarGroup of activity owners with tooltips.
 * Data: step.activity_owners [{id, first_name, last_name, full_name, email}].
 */
function UsersInvolvedSection({ owners }) {
  const theme = useTheme();

  const users = owners || [];

  // Generate initials from name
  const getInitials = (user) => {
    const first = user.first_name?.[0] || '';
    const last = user.last_name?.[0] || '';
    return (first + last).toUpperCase() || user.email?.[0]?.toUpperCase() || '?';
  };

  // Deterministic color from string
  const getAvatarColor = (name) => {
    const colors = [
      theme.palette.primary.main,
      theme.palette.secondary.main,
      theme.palette.success.main,
      theme.palette.warning.main,
      theme.palette.info.main,
      theme.palette.error.main
    ];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <Box>
      <Typography variant="overline" color="text.secondary" gutterBottom display="block">
        Users Involved
      </Typography>

      {users.length === 0 ? (
        <Typography variant="body2" color="text.disabled" fontStyle="italic">
          No users involved yet
        </Typography>
      ) : (
        <Stack direction="row" spacing={1.5} alignItems="center">
          <AvatarGroup
            max={6}
            sx={{
              '& .MuiAvatar-root': {
                width: 32,
                height: 32,
                fontSize: '0.75rem',
                border: `2px solid ${theme.palette.background.paper}`
              }
            }}
          >
            {users.map((user) => (
              <Tooltip key={user.id} title={user.full_name || user.email} arrow>
                <MuiAvatar
                  sx={{
                    bgcolor: getAvatarColor(user.full_name || user.email || ''),
                    cursor: 'default'
                  }}
                >
                  {getInitials(user)}
                </MuiAvatar>
              </Tooltip>
            ))}
          </AvatarGroup>

          <Typography variant="body2" color="text.secondary">
            {users.length} user{users.length !== 1 ? 's' : ''}
          </Typography>
        </Stack>
      )}
    </Box>
  );
}

UsersInvolvedSection.propTypes = {
  owners: PropTypes.array
};

// ==============================|| ACTIVITY TIMELINE DOTS ||============================== //

/**
 * Horizontal timeline with colored dots for each activity.
 * Dots colored by status: COMPLETED=green, PLANNED=blue, overdue=red, CANCELLED=grey.
 * Connected by a line. Start/end dates shown below.
 *
 * Uses useGetActivitiesByStep hook (Option A — no backend change).
 */

function getActivityDotColor(activity, theme) {
  if (activity.status === 'COMPLETED') return theme.palette.success.main;
  if (activity.status === 'CANCELLED') return theme.palette.grey[400];
  // PLANNED — check if overdue
  if (activity.status === 'PLANNED') {
    const dueDate = activity.due_date || activity.scheduled_date;
    if (dueDate && new Date(dueDate) < new Date()) {
      return theme.palette.error.main;
    }
    return theme.palette.info.main;
  }
  return theme.palette.grey[400];
}

function getActivityDotTooltip(activity) {
  const title = activity.title || 'Activity';
  const status = activity.status_display || activity.status || '';
  const date = activity.scheduled_date
    ? new Date(activity.scheduled_date).toLocaleDateString()
    : 'No date';
  return `${title} — ${status} (${date})`;
}

function ActivityTimelineSection({ stepId, startDate, endDate }) {
  const theme = useTheme();

  const { activities, activitiesLoading } = useGetActivitiesByStep(stepId, {
    pageSize: 20,
    ordering: 'scheduled_date'
  });

  // Sort activities by date (ascending) — exclude cancelled for timeline
  const sortedActivities = useMemo(() => {
    if (!activities?.length) return [];
    return [...activities]
      .filter((a) => a.status !== 'CANCELLED')
      .sort((a, b) => {
        const dateA = a.scheduled_date || a.due_date || a.created_at || '';
        const dateB = b.scheduled_date || b.due_date || b.created_at || '';
        return dateA.localeCompare(dateB);
      });
  }, [activities]);

  // Format date helper
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <Box>
      {activitiesLoading ? (
        <Typography variant="body2" color="text.disabled">
          Loading activities...
        </Typography>
      ) : sortedActivities.length === 0 ? (
        <Typography variant="body2" color="text.disabled" fontStyle="italic">
          No activities yet
        </Typography>
      ) : (
        <Stack spacing={1.5}>
            {/* Timeline dots row */}
            <Box sx={{ position: 'relative', display: 'flex', alignItems: 'center', py: 1, px: 1.5 }}>
              {/* Connecting line */}
              <Box
                sx={{
                  position: 'absolute',
                  top: '50%',
                  left: 20,
                  right: 20,
                  height: 2,
                  bgcolor: theme.palette.grey[300],
                  transform: 'translateY(-50%)',
                  zIndex: 0
                }}
              />

              {/* Dots — space-evenly ensures dots are never at extremes */}
              <Stack
                direction="row"
                sx={{
                  width: '100%',
                  justifyContent: 'space-evenly',
                  position: 'relative',
                  zIndex: 1
                }}
              >
                {sortedActivities.map((activity) => {
                  const dotColor = getActivityDotColor(activity, theme);
                  const tooltip = getActivityDotTooltip(activity);

                  return (
                    <Tooltip key={activity.id} title={tooltip} arrow>
                      <Box
                        sx={{
                          width: 14,
                          height: 14,
                          borderRadius: '50%',
                          bgcolor: dotColor,
                          border: `2px solid ${theme.palette.background.paper}`,
                          boxShadow: `0 0 0 1px ${dotColor}`,
                          cursor: 'default',
                          flexShrink: 0
                        }}
                      />
                    </Tooltip>
                  );
                })}
              </Stack>
            </Box>

            {/* Date labels below */}
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="caption" color="text.secondary">
                {formatDate(startDate)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {formatDate(endDate)}
              </Typography>
            </Stack>

            {/* Legend */}
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              {[
                { label: 'Completed', color: theme.palette.success.main },
                { label: 'Planned', color: theme.palette.info.main },
                { label: 'Overdue', color: theme.palette.error.main }
              ].map((item) => (
                <Stack key={item.label} direction="row" spacing={0.5} alignItems="center">
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      bgcolor: item.color
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {item.label}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Stack>
        )}
    </Box>
  );
}

ActivityTimelineSection.propTypes = {
  stepId: PropTypes.string,
  startDate: PropTypes.string,
  endDate: PropTypes.string
};

// ==============================|| CONTEXT SECTION (editable) ||============================== //

function ContextSection({ step, handleSaveField }) {
  const theme = useTheme();

  return (
    <Box>
      <SectionHeader icon={FileTextOutlined} title="Context" />

      <Box
        sx={{
          p: 2,
          borderRadius: 1,
          bgcolor: 'grey.50',
          border: '1px solid',
          borderColor: 'grey.200'
        }}
      >
        <Stack spacing={2.5}>
          {/* Row 1: Description + Goal (side by side on desktop) */}
          <Grid container spacing={2.5}>
            <Grid item xs={12} md={6}>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                Description
              </Typography>
              <EditableTextArea
                value={step?.description}
                fieldKey="description"
                onSave={handleSaveField}
                placeholder="What will be done in this step?"
                emptyText="No description"
                minRows={2}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                Goal
              </Typography>
              <EditableTextArea
                value={step?.goal}
                fieldKey="goal"
                onSave={handleSaveField}
                placeholder="What this step aims to achieve?"
                emptyText="No goal defined"
                minRows={2}
              />
            </Grid>
          </Grid>

          {/* Row 2: Criterias + Metrics (side by side) */}
          <Grid container spacing={2.5}>
            <Grid item xs={12} md={6}>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                Criterias
              </Typography>
              <EditableChipList
                values={step?.criterias || []}
                fieldKey="criterias"
                onSave={handleSaveField}
                placeholder="Add criteria..."
                emptyText="No criterias defined"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                Metrics
              </Typography>
              <EditableChipList
                values={step?.metrics || []}
                fieldKey="metrics"
                onSave={handleSaveField}
                placeholder="Add metric..."
                emptyText="No metrics defined"
              />
            </Grid>
          </Grid>
        </Stack>
      </Box>
    </Box>
  );
}

ContextSection.propTypes = {
  step: PropTypes.object,
  handleSaveField: PropTypes.func.isRequired
};

// ==============================|| DECISION STEP OVERVIEW TAB (MAIN) ||============================== //

export default function DecisionStepOverviewTab({ step, account, onUpdate }) {
  // Derive accountId
  const accountId = account?.id || step?.account_id;

  // ==============================|| SHARED EDIT HOOK ||============================== //

  const {
    saving,
    handleSaveField,
    handleSaveManagerNotes,
    handleDeleteManagerNotes
  } = useDecisionStepEdit({ step, accountId, onUpdate });

  // ==============================|| PERMISSIONS ||============================== //

  const { currentUserId, isAdmin, isManager } = useUserPermissions();

  const stepOwnerId = step?.owner_id || step?.owner;
  const canViewNotes = canViewManagerNotes({
    resourceOwnerId: stepOwnerId,
    currentUserId,
    isAdmin,
    isManager
  });
  const canEditNotes = canEditManagerNotes({ isAdmin, isManager });

  // ==============================|| DERIVED DATA ||============================== //

  const completenessScore = step?.completeness_score || 0;
  const completenessSuggestions = step?.completeness_details?.suggestions || [];
  const startDate = step?.effective_start_date || step?.start_date;
  const endDate = step?.completed_at || step?.effective_end_date || step?.expected_end;

  // ==============================|| RENDER ||============================== //

  return (
    <Stack spacing={3}>
      {/* ==================== SECTION 1: Step Intelligence (paired like People) ==================== */}
      <Box>
        <SectionHeader icon={TeamOutlined} title="Step Intelligence" />

        <Grid container spacing={3} alignItems="stretch">
          <Grid item xs={12} md={6} sx={{ display: 'flex' }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 1,
                bgcolor: 'grey.50',
                border: '1px solid',
                borderColor: 'grey.200',
                width: '100%',
                minHeight: 180
              }}
            >
              <ContactsInvolvedSection contacts={step?.all_contacts} />
            </Box>
          </Grid>

          <Grid item xs={12} md={6} sx={{ display: 'flex' }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 1,
                bgcolor: 'grey.50',
                border: '1px solid',
                borderColor: 'grey.200',
                width: '100%',
                minHeight: 180
              }}
            >
              <UsersInvolvedSection owners={step?.activity_owners} />
            </Box>
          </Grid>
        </Grid>
      </Box>

      {/* ==================== SECTION 2: Documentation Readiness (own Card — no wrapper) ==================== */}
      <CompletenessScoreWidget
        score={completenessScore}
        suggestions={completenessSuggestions}
        variant="full"
        defaultExpanded={false}
      />

      {/* ==================== SECTION 3: Manager Notes (own styling — no wrapper) ==================== */}
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

      {/* ==================== SECTION 4: Activity Timeline ==================== */}
      <Box>
        <SectionHeader icon={NodeIndexOutlined} title="Activity Timeline" />

        <Box
          sx={{
            p: 2,
            borderRadius: 1,
            bgcolor: 'grey.50',
            border: '1px solid',
            borderColor: 'grey.200'
          }}
        >
          <ActivityTimelineSection
            stepId={step?.id}
            startDate={startDate}
            endDate={endDate}
          />
        </Box>
      </Box>

      {/* ==================== SECTION 5: Context ==================== */}
      <ContextSection step={step} handleSaveField={handleSaveField} />
    </Stack>
  );
}

DecisionStepOverviewTab.propTypes = {
  step: PropTypes.object.isRequired,
  account: PropTypes.object,
  onUpdate: PropTypes.func
};