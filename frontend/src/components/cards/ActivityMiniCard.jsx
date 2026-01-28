// frontend/src/components/cards/ActivityMiniCard.jsx
/**
 * ActivityMiniCard Component
 * 
 * Displays a compact activity card with type icon, title, status, and date.
 * Used for showing linked activities (previous/next) and activity lists.
 * 
 * Used in:
 * - Activity Overview (Previous/Next Activity)
 * - Activity Outcome Tab (Next Activity)
 * - Decision Step (Activity list)
 */

'use client';

import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// MUI
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Project imports
import RemovableCard from './RemovableCard';

// Icons
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import LinkedinOutlined from '@ant-design/icons/LinkedinOutlined';
import QuestionCircleOutlined from '@ant-design/icons/QuestionCircleOutlined';
import LinkOutlined from '@ant-design/icons/LinkOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';

// ==============================|| CONSTANTS ||============================== //

const TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined
};

const TYPE_LABELS = {
  CALL: 'Call',
  EMAIL: 'Email',
  MEETING: 'Meeting',
  TASK: 'Task',
  LINKEDIN: 'LinkedIn',
  OTHER: 'Other'
};

const STATUS_LABELS = {
  PLANNED: 'Planned',
  IN_PROGRESS: 'In Progress',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled'
};

const STATUS_COLORS = {
  PLANNED: 'default',
  IN_PROGRESS: 'info',
  COMPLETED: 'success',
  CANCELLED: 'error'
};

// ==============================|| ACTIVITY MINI CARD ||============================== //

export default function ActivityMiniCard({
  activity,
  label,
  onUnlink,
  unlinkTooltip = 'Unlink',
  showDate = true,
  showStatus = true,
  showTypeIcon = true,
  variant = 'default',
  size = 'medium',
  navigateOnClick = true,
  emptyText = 'None',
  sx = {}
}) {
  const router = useRouter();

  // Empty state
  if (!activity) {
    return (
      <Box sx={sx}>
        {label && (
          <Typography variant="caption" color="text.secondary" gutterBottom display="block">
            {label}
          </Typography>
        )}
        <Typography variant="body2" color="text.secondary" fontStyle="italic">
          {emptyText}
        </Typography>
      </Box>
    );
  }

  // Size configurations
  const sizeConfig = {
    small: {
      iconSize: 14,
      titleVariant: 'body2',
      metaVariant: 'caption',
      chipSize: 'small',
      padding: 1
    },
    medium: {
      iconSize: 18,
      titleVariant: 'body2',
      metaVariant: 'caption',
      chipSize: 'small',
      padding: 1.5
    },
    large: {
      iconSize: 22,
      titleVariant: 'subtitle2',
      metaVariant: 'body2',
      chipSize: 'medium',
      padding: 2
    }
  };

  const config = sizeConfig[size];

  // Get icon component
  const TypeIcon = TYPE_ICONS[activity.activity_type] || QuestionCircleOutlined;

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
    });
  };

  // Handle navigation
  const handleClick = () => {
    if (navigateOnClick && activity.id) {
      router.push(`/activities/${activity.id}`);
    }
  };

  // Build metadata line
  const metaParts = [
    TYPE_LABELS[activity.activity_type] || activity.activity_type,
    showDate && activity.scheduled_date && formatDate(activity.scheduled_date)
  ].filter(Boolean);

  return (
    <Box sx={sx}>
      {/* Optional label above card */}
      {label && (
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          {label}
        </Typography>
      )}

      <RemovableCard
        onRemove={onUnlink}
        removeTooltip={unlinkTooltip}
        variant={variant}
        onClick={navigateOnClick ? handleClick : undefined}
        sx={{ p: config.padding }}
      >
        {/* Type Icon or Link Icon */}
        {showTypeIcon ? (
          <Box 
            sx={{ 
              display: 'flex', 
              alignItems: 'center',
              color: 'warning.main'
            }}
          >
            <TypeIcon style={{ fontSize: config.iconSize }} />
          </Box>
        ) : (
          <LinkOutlined style={{ fontSize: config.iconSize, color: '#faad14' }} />
        )}

        {/* Activity info */}
        <Box flex={1} minWidth={0}>
          <Typography 
            variant={config.titleVariant} 
            fontWeight={500} 
            color={navigateOnClick ? 'primary.main' : 'text.primary'}
            noWrap
            sx={navigateOnClick ? { 
              cursor: 'pointer',
              '&:hover': { textDecoration: 'underline' }
            } : {}}
          >
            {activity.title}
          </Typography>
          
          {metaParts.length > 0 && (
            <Stack direction="row" spacing={0.5} alignItems="center">
              <Typography variant={config.metaVariant} color="text.secondary">
                {metaParts.join(' • ')}
              </Typography>
            </Stack>
          )}
        </Box>

        {/* Status chip */}
        {showStatus && activity.status && (
          <Chip
            label={STATUS_LABELS[activity.status] || activity.status}
            color={STATUS_COLORS[activity.status] || 'default'}
            size={config.chipSize}
            variant="outlined"
          />
        )}
      </RemovableCard>
    </Box>
  );
}

ActivityMiniCard.propTypes = {
  /** Activity object */
  activity: PropTypes.shape({
    id: PropTypes.string,
    title: PropTypes.string,
    activity_type: PropTypes.string,
    status: PropTypes.string,
    scheduled_date: PropTypes.string
  }),
  /** Label displayed above the card */
  label: PropTypes.string,
  /** Callback when unlink/remove button is clicked */
  onUnlink: PropTypes.func,
  /** Tooltip for unlink button */
  unlinkTooltip: PropTypes.string,
  /** Show scheduled date */
  showDate: PropTypes.bool,
  /** Show status chip */
  showStatus: PropTypes.bool,
  /** Show type icon */
  showTypeIcon: PropTypes.bool,
  /** Visual variant */
  variant: PropTypes.oneOf(['default', 'outlined', 'filled']),
  /** Size variant */
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  /** Navigate to activity on click */
  navigateOnClick: PropTypes.bool,
  /** Text to show when activity is null */
  emptyText: PropTypes.string,
  /** Additional styles */
  sx: PropTypes.object
};