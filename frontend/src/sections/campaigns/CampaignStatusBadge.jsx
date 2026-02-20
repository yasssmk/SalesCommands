// frontend/src/sections/campaigns/CampaignStatusBadge.jsx

import PropTypes from 'prop-types';

// material-ui
import Chip from '@mui/material/Chip';

// icons
import EditOutlined from '@ant-design/icons/EditOutlined';
import PlayCircleOutlined from '@ant-design/icons/PlayCircleOutlined';
import PauseCircleOutlined from '@ant-design/icons/PauseCircleOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';

// ==============================|| STATUS CONFIGURATION ||============================== //

/**
 * Status config mapping
 * Maps campaign status to label, MUI color, and icon
 */
const STATUS_CONFIG = {
  DRAFT: {
    label: 'Draft',
    color: 'default',
    icon: EditOutlined
  },
  ACTIVE: {
    label: 'Active',
    color: 'success',
    icon: PlayCircleOutlined
  },
  PAUSED: {
    label: 'Paused',
    color: 'warning',
    icon: PauseCircleOutlined
  },
  COMPLETED: {
    label: 'Completed',
    color: 'primary',
    icon: CheckCircleOutlined
  },
  CANCELLED: {
    label: 'Cancelled',
    color: 'error',
    icon: CloseCircleOutlined
  }
};

// ==============================|| CAMPAIGN STATUS BADGE ||============================== //

/**
 * CampaignStatusBadge Component
 *
 * Displays a colored chip with icon for campaign status.
 * Reusable across CampaignCard, workspace header, list views.
 *
 * @component
 * @example
 * <CampaignStatusBadge status="ACTIVE" />
 * <CampaignStatusBadge status="DRAFT" size="medium" />
 * <CampaignStatusBadge status="COMPLETED" variant="outlined" />
 */
export default function CampaignStatusBadge({ status, size = 'small', variant = 'filled' }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.DRAFT;
  const IconComponent = config.icon;

  return (
    <Chip
      label={config.label}
      color={config.color}
      size={size}
      variant={variant}
      icon={<IconComponent />}
      sx={{
        fontWeight: 500,
        '& .MuiChip-icon': {
          fontSize: '1rem'
        }
      }}
    />
  );
}

// ==============================|| PROP TYPES ||============================== //

CampaignStatusBadge.propTypes = {
  /** Campaign status value */
  status: PropTypes.oneOf(['DRAFT', 'ACTIVE', 'PAUSED', 'COMPLETED', 'CANCELLED']).isRequired,
  /** Chip size */
  size: PropTypes.oneOf(['small', 'medium']),
  /** Visual style variant */
  variant: PropTypes.oneOf(['filled', 'outlined'])
};