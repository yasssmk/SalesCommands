// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepHeader.jsx
/**
 * Decision Step Header Component
 *
 * Standardized workspace header following ActivityHeader pattern:
 * - Row 1: Stage avatar + Step name (read-only)
 * - Row 2: Derived status chip
 * - Divider
 * - Row 3: Account > Cycle · Timeline · Progression
 *
 * No actions menu — step status is 100% derived from activities.
 * No editable name — step name = stage label (fixed pipeline).
 */

'use client';

import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// MUI
import { useTheme } from '@mui/material/styles';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// Date formatting
import { format } from 'date-fns';

// Project imports
import MainCard from 'components/MainCard';
import { PIPELINE_STEP_LABELS } from 'api/accounts/decisionCycles';

// Icons
import {
  SearchOutlined,
  ToolOutlined,
  SolutionOutlined,
  DollarOutlined,
  FileProtectOutlined,
  SettingOutlined,
  RocketOutlined,
  BankOutlined,
  RightOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';

// ==============================|| STAGE CONFIGURATION ||============================== //

/**
 * Stage → Avatar icon + color mapping.
 * Same pattern as TYPE_ICONS / TYPE_AVATAR_COLORS in ActivityHeader.
 */
const STAGE_ICONS = {
  QUALIFICATION: SearchOutlined,
  TECHNICAL_FIT: ToolOutlined,
  SOLUTION_VALIDATION: SolutionOutlined,
  BUSINESS_CASE: DollarOutlined,
  CLOSING: FileProtectOutlined,
  IMPLEMENTATION: SettingOutlined,
  GO_LIVE: RocketOutlined
};

const STAGE_AVATAR_COLORS = {
  QUALIFICATION: 'info.main',
  TECHNICAL_FIT: 'secondary.main',
  SOLUTION_VALIDATION: 'success.main',
  BUSINESS_CASE: 'warning.main',
  CLOSING: 'primary.main',
  IMPLEMENTATION: 'grey.500',
  GO_LIVE: 'success.dark'
};

/**
 * Status config for display — read-only, derived by backend.
 */
const STATUS_CONFIG = {
  WON: { label: 'Won', color: 'primary' },
  REJECTED: { label: 'Rejected', color: 'error' },
  OVERDUE: { label: 'Overdue', color: 'error' },
  VALIDATED: { label: 'Validated', color: 'primary' },
  IN_PROGRESS: { label: 'In Progress', color: 'secondary' },
  ON_HOLD: { label: 'On Hold', color: 'warning' },
  IN_CHASING: { label: 'In Chasing', color: 'warning' },
  NOT_STARTED: { label: 'Not Started', color: 'default' }
};

// ==============================|| STEP HEADER SKELETON ||============================== //

function StepHeaderSkeleton() {
  return (
    <MainCard sx={{ mb: 0, borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}>
      <Stack spacing={2}>
        {/* Row 1: Avatar + Title */}
        <Stack direction="row" alignItems="center" spacing={2}>
          <Skeleton variant="circular" width={56} height={56} />
          <Skeleton variant="text" width={220} height={40} />
        </Stack>

        {/* Row 2: Chips */}
        <Stack direction="row" spacing={1}>
          <Skeleton variant="rectangular" width={90} height={24} sx={{ borderRadius: 4 }} />
        </Stack>

        {/* Divider */}
        <Divider />

        {/* Row 3: Info items */}
        <Stack direction="row" spacing={3}>
          <Skeleton variant="text" width={150} height={20} />
          <Skeleton variant="text" width={120} height={20} />
          <Skeleton variant="text" width={60} height={20} />
        </Stack>
      </Stack>
    </MainCard>
  );
}

// ==============================|| STEP HEADER ||============================== //

export default function StepHeader({ step, account, cycleId, cycleName, loading }) {
  const theme = useTheme();
  const router = useRouter();

  // ==============================|| LOADING STATE ||============================== //

  if (loading) {
    return <StepHeaderSkeleton />;
  }

  // ==============================|| NO DATA STATE ||============================== //

  if (!step) {
    return null;
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const StageIcon = STAGE_ICONS[step.stage] || SearchOutlined;
  const avatarColor = STAGE_AVATAR_COLORS[step.stage] || 'grey.500';
  const statusConfig = STATUS_CONFIG[step.derived_status] || STATUS_CONFIG.NOT_STARTED;
  const stepName = step.name || PIPELINE_STEP_LABELS[step.stage] || step.stage;

  // Activity progression (from backend serializer fields)
  const totalActivities = step.activities_count || step.activities?.length || 0;
  const completedActivities = step.completed_activities_count ?? (
    step.activities ? step.activities.filter(a => a.status === 'COMPLETED').length : null
  );

  // Timeline dates
  const startDate = step.effective_start_date || step.start_date;
  const endDate = step.completed_at || step.effective_end_date || step.expected_end;
  const isCompleted = ['VALIDATED', 'WON', 'REJECTED'].includes(step.derived_status);

  // Account info
  const accountName = account?.company_name;
  const accountId = account?.id || step.account_id;

  // ==============================|| HANDLERS ||============================== //

  const handleAccountClick = () => {
    if (accountId) {
      router.push(`/accounts/${accountId}?tab=decision-cycle`);
    }
  };

  // ==============================|| FORMAT HELPERS ||============================== //

  const formatShortDate = (dateStr) => {
    if (!dateStr) return null;
    return format(new Date(dateStr), 'MMM d, yyyy');
  };

  const renderTimeline = () => {
    // Closed step: show completed date only (same pattern as ActivityHeader renderDateInfo)
    if (isCompleted && step.completed_at) {
      const completedColor = step.derived_status === 'REJECTED'
        ? theme.palette.error.main
        : theme.palette.success.main;
      return (
        <Stack direction="row" spacing={0.75} alignItems="center">
          <CheckCircleOutlined style={{ fontSize: theme.iconSizes.sm, color: completedColor, display: 'flex' }} />
          <Typography variant="body2" sx={{ color: completedColor }}>
            Closed {format(new Date(step.completed_at), 'MMM d, yyyy HH:mm')}
          </Typography>
        </Stack>
      );
    }

    // Active step: show Start → End
    if (!startDate && !endDate) return null;

    const startText = startDate ? formatShortDate(startDate) : '—';
    const endText = endDate ? formatShortDate(endDate) : '—';

    const isOverdue = !isCompleted && step.expected_end && new Date(step.expected_end) < new Date();
    const isOnHold = step.derived_status === 'ON_HOLD';

    let endColor = theme.palette.text.secondary;
    if (isOnHold) {
      endColor = theme.palette.warning.main;
    } else if (isOverdue) {
      endColor = theme.palette.error.main;
    }

    return (
      <Stack direction="row" spacing={0.75} alignItems="center">
        <CalendarOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.text.secondary, display: 'flex' }} />
        <Typography variant="body2" color="text.secondary">
          {startText}
        </Typography>
        <RightOutlined style={{ fontSize: theme.iconSizes.xs - 2, color: theme.palette.text.disabled }} />
        <Tooltip title={isOnHold ? 'On Hold' : isOverdue ? 'Overdue' : 'Expected end'}>
          <Typography
            variant="body2"
            sx={{
              color: endColor,
              fontWeight: isOverdue ? theme.typography.fontWeightMedium : theme.typography.fontWeightRegular
            }}
          >
            {endText}
            {isOverdue && !isOnHold && ' (Overdue)'}
          </Typography>
        </Tooltip>
      </Stack>
    );
  };

  // ==============================|| RENDER ||============================== //

  return (
    <MainCard sx={{ mb: 0, borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}>
      <Stack spacing={2}>
        {/* Row 1: Stage Avatar + Step Name */}
        <Stack direction="row" alignItems="center" spacing={2} sx={{ flexWrap: 'wrap' }}>
          <Avatar
            sx={{
              width: 56,
              height: 56,
              bgcolor: avatarColor,
              fontSize: '1.5rem'
            }}
          >
            <StageIcon />
          </Avatar>

          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="h3" component="h1" noWrap>
              {stepName}
            </Typography>
          </Box>
        </Stack>

        {/* Row 2: Status Chip */}
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip
            label={step.derived_status_display || statusConfig.label}
            color={statusConfig.color}
            size="small"
            variant="filled"
          />
        </Stack>

        {/* Divider */}
        <Divider />

        {/* Row 3: Account > Cycle · Timeline · Progression */}
        <Stack direction="row" spacing={3} alignItems="center" flexWrap="wrap" useFlexGap>
          {/* Account > Cycle (both clickable) */}
          {accountName && (
            <Stack direction="row" spacing={0.75} alignItems="center">
              <BankOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.text.secondary, display: 'flex' }} />
              <Typography
                variant="body2"
                color="primary.main"
                onClick={handleAccountClick}
                sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
              >
                {accountName}
              </Typography>
              {cycleName && (
                <>
                  <RightOutlined style={{ fontSize: theme.iconSizes.xs - 2, color: theme.palette.text.disabled }} />
                  <Typography
                    variant="body2"
                    color="primary.main"
                    onClick={handleAccountClick}
                    sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                  >
                    {cycleName}
                  </Typography>
                </>
              )}
            </Stack>
          )}

          {/* Timeline: Start → End OR Closed date */}
          {renderTimeline()}

          {/* Progression: completed/total (only when data available) */}
          {totalActivities > 0 && completedActivities !== null && (
            <Stack direction="row" spacing={0.75} alignItems="center">
              <CheckCircleOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.success.main, display: 'flex' }} />
              <Typography variant="body2" color="text.secondary">
                {completedActivities}/{totalActivities}
              </Typography>
            </Stack>
          )}
        </Stack>
      </Stack>
    </MainCard>
  );
}

// ==============================|| PROP TYPES ||============================== //

StepHeader.propTypes = {
  step: PropTypes.object,
  account: PropTypes.object,
  cycleId: PropTypes.string,
  cycleName: PropTypes.string,
  loading: PropTypes.bool
};