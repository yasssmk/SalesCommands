// frontend/src/components/cards/UserCard.jsx
/**
 * UserCard Component
 * 
 * Displays an internal user with avatar, name, and email.
 * Supports edit and remove actions.
 * 
 * Used in:
 * - Activity Overview (Owner, Invited Users)
 * - Decision Step (Owner)
 * - Team assignments
 */

'use client';

import { useState } from 'react';
import PropTypes from 'prop-types';

// MUI
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';

// Icons
import UserOutlined from '@ant-design/icons/UserOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// ==============================|| HELPERS ||============================== //

/**
 * Get initials from user name
 */
function getUserInitials(user) {
  if (!user) return '?';
  
  const name = user.full_name || `${user.first_name || ''} ${user.last_name || ''}`.trim();
  if (!name) return user.email?.[0]?.toUpperCase() || '?';
  
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) {
    return parts[0].substring(0, 2).toUpperCase();
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Get display name from user object
 */
function getUserDisplayName(user) {
  if (!user) return 'Unknown';
  return user.full_name || `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email || 'Unknown';
}

// ==============================|| USER CARD ||============================== //

export default function UserCard({
  user,
  label,
  onEdit,
  onRemove,
  showEmail = true,
  showAvatar = true,
  size = 'medium',
  variant = 'default',
  avatarColor = 'primary',
  sx = {}
}) {
  const theme = useTheme();
  const [hovered, setHovered] = useState(false);

  if (!user) {
    return (
      <Box sx={sx}>
        {label && (
          <Typography variant="caption" color="text.secondary" gutterBottom display="block">
            {label}
          </Typography>
        )}
        <Typography variant="body2" color="text.disabled" fontStyle="italic">
          No user assigned
        </Typography>
      </Box>
    );
  }

  // Size configurations
  const sizeConfig = {
    small: {
      avatarSize: 28,
      iconSize: 16,
      nameVariant: 'body2',
      emailVariant: 'caption',
      padding: 1
    },
    medium: {
      avatarSize: 36,
      iconSize: 20,
      nameVariant: 'body2',
      emailVariant: 'caption',
      padding: 1.5
    },
    large: {
      avatarSize: 44,
      iconSize: 24,
      nameVariant: 'subtitle1',
      emailVariant: 'body2',
      padding: 2
    }
  };

  const config = sizeConfig[size];
  const displayName = getUserDisplayName(user);
  const initials = getUserInitials(user);

  // Variant styles
  const variantStyles = {
    default: {
      bgcolor: 'grey.50',
      border: '1px solid',
      borderColor: 'grey.200',
      '&:hover': { 
        borderColor: 'grey.300' 
      }
    },
    outlined: {
      bgcolor: 'background.paper',
      border: '1px solid',
      borderColor: 'divider',
      '&:hover': { 
        borderColor: 'primary.light',
        bgcolor: alpha(theme.palette.primary.main, 0.02)
      }
    },
    filled: {
      bgcolor: 'grey.100',
      border: 'none',
      '&:hover': { 
        bgcolor: 'grey.200' 
      }
    }
  };

  return (
    <Box sx={sx}>
      {/* Optional label above card */}
      {label && (
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          {label}
        </Typography>
      )}
      
      <Box
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        sx={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          p: config.padding,
          borderRadius: 1,
          transition: 'all 0.2s ease',
          ...variantStyles[variant]
        }}
      >
        {/* Avatar or Icon */}
        {showAvatar ? (
          <Avatar
            src={user.avatar}
            alt={displayName}
            sx={{
              width: config.avatarSize,
              height: config.avatarSize,
              bgcolor: `${avatarColor}.main`,
              fontSize: config.avatarSize * 0.4
            }}
          >
            {initials}
          </Avatar>
        ) : (
          <UserOutlined style={{ fontSize: config.iconSize, color: theme.palette.primary.main }} />
        )}

        {/* User info */}
        <Box flex={1} minWidth={0}>
          <Typography 
            variant={config.nameVariant} 
            fontWeight={500} 
            noWrap
          >
            {displayName}
          </Typography>
          {showEmail && user.email && (
            <Typography 
              variant={config.emailVariant} 
              color="text.secondary" 
              noWrap
            >
              {user.email}
            </Typography>
          )}
        </Box>

        {/* Action buttons - show on hover */}
        {hovered && (onEdit || onRemove) && (
          <Box
            sx={{
              position: 'absolute',
              top: 4,
              right: 4,
              display: 'flex',
              gap: 0.25
            }}
          >
            {/* Edit button */}
            {onEdit && (
              <Tooltip title="Change">
                <IconButton 
                  size="small" 
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit();
                  }}
                  sx={{
                    width: 20,
                    height: 20,
                    bgcolor: 'background.paper',
                    boxShadow: 1,
                    '&:hover': { 
                      bgcolor: 'primary.lighter', 
                      color: 'primary.main' 
                    }
                  }}
                >
                  <EditOutlined style={{ fontSize: 10 }} />
                </IconButton>
              </Tooltip>
            )}

            {/* Remove button */}
            {onRemove && (
              <Tooltip title="Remove">
                <IconButton 
                  size="small" 
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove();
                  }}
                  sx={{
                    width: 20,
                    height: 20,
                    bgcolor: 'background.paper',
                    boxShadow: 1,
                    '&:hover': { 
                      bgcolor: 'error.lighter', 
                      color: 'error.main' 
                    }
                  }}
                >
                  <CloseOutlined style={{ fontSize: 10 }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
}

UserCard.propTypes = {
  /** User object with id, full_name/first_name/last_name, email, avatar */
  user: PropTypes.shape({
    id: PropTypes.string,
    full_name: PropTypes.string,
    first_name: PropTypes.string,
    last_name: PropTypes.string,
    email: PropTypes.string,
    avatar: PropTypes.string
  }),
  /** Label displayed above the card */
  label: PropTypes.string,
  /** Callback when edit button is clicked */
  onEdit: PropTypes.func,
  /** Callback when remove button is clicked */
  onRemove: PropTypes.func,
  /** Whether to show the email */
  showEmail: PropTypes.bool,
  /** Whether to show avatar (vs icon) */
  showAvatar: PropTypes.bool,
  /** Size variant */
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  /** Visual variant */
  variant: PropTypes.oneOf(['default', 'outlined', 'filled']),
  /** Avatar background color */
  avatarColor: PropTypes.string,
  /** Additional styles */
  sx: PropTypes.object
};