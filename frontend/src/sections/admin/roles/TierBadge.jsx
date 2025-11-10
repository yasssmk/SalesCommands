// frontend/src/sections/admin/roles/TierBadge.jsx

import PropTypes from 'prop-types';

// material-ui
import Chip from '@mui/material/Chip';

// ant design icons
import SafetyOutlined from '@ant-design/icons/SafetyOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';

/**
 * TierBadge Component
 * 
 * Displays a colored badge with icon for user role tier.
 * 
 * Tier variants:
 * - admin: Red badge with security icon (highest privilege)
 * - manager: Orange badge with group icon (team management)
 * - individual: Green badge with person icon (standard user)
 * 
 * @component
 * @example
 * <TierBadge tier="admin" />
 * <TierBadge tier="manager" size="small" />
 * <TierBadge tier="individual" />
 */
function TierBadge({ tier, size = 'small', variant = 'filled' }) {
  // ==============================|| TIER CONFIGURATION ||============================== //
  
  const getTierConfig = (tierValue) => {
    const configs = {
      admin: {
        label: 'Admin',
        color: 'error',
        icon: SafetyOutlined
      },
      manager: {
        label: 'Manager',
        color: 'warning',
        icon: TeamOutlined
      },
      individual: {
        label: 'Individual',
        color: 'success',
        icon: UserOutlined
      }
    };

    return configs[tierValue] || {
      label: 'Unknown',
      color: 'default',
      icon: UserOutlined
    };
  };

  const config = getTierConfig(tier);
  const IconComponent = config.icon;

  // ==============================|| RENDER ||============================== //

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

TierBadge.propTypes = {
  /**
   * The tier level to display
   * @type {'admin' | 'manager' | 'individual'}
   */
  tier: PropTypes.oneOf(['admin', 'manager', 'individual']).isRequired,
  
  /**
   * Size of the chip
   * @type {'small' | 'medium'}
   */
  size: PropTypes.oneOf(['small', 'medium']),
  
  /**
   * Visual style variant
   * @type {'filled' | 'outlined'}
   */
  variant: PropTypes.oneOf(['filled', 'outlined'])
};

export default TierBadge;