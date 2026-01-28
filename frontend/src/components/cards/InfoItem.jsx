// frontend/src/components/cards/InfoItem.jsx
/**
 * InfoItem Component
 * 
 * Displays a piece of information with optional icon and label.
 * Used in headers and detail views for compact info display.
 * 
 * Formats:
 * - With label: "📅 Due: Jan 28, 2026"
 * - Without label: "📅 Jan 28, 2026"
 * - Clickable: underline on hover
 * 
 * Used in:
 * - Activity Header (dates, account, owner)
 * - Account Header (location, owner, team)
 * - Any header or summary section
 */

'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';

// ==============================|| INFO ITEM ||============================== //

export default function InfoItem({
  icon: Icon,
  label,
  value,
  color = 'text.secondary',
  valueColor,
  onClick,
  tooltip,
  size = 'medium',
  emptyText = '—',
  sx = {}
}) {
  // Size configurations
  const sizeConfig = {
    small: {
      iconSize: 12,
      variant: 'caption',
      spacing: 0.5
    },
    medium: {
      iconSize: 14,
      variant: 'body2',
      spacing: 0.75
    },
    large: {
      iconSize: 16,
      variant: 'body1',
      spacing: 1
    }
  };

  const config = sizeConfig[size];
  const displayValue = value || emptyText;
  const isEmpty = !value;

  const content = (
    <Stack 
      direction="row" 
      spacing={config.spacing} 
      alignItems="center"
      onClick={onClick}
      sx={{
        cursor: onClick ? 'pointer' : 'default',
        '&:hover': onClick ? {
          '& .info-value': { textDecoration: 'underline' }
        } : {},
        ...sx
      }}
    >
      {/* Icon */}
      {Icon && (
        <Box 
          component="span" 
          sx={{ 
            display: 'flex', 
            alignItems: 'center',
            color: color 
          }}
        >
          <Icon style={{ fontSize: config.iconSize }} />
        </Box>
      )}
      
      {/* Label + Value */}
      <Typography 
        variant={config.variant} 
        color={isEmpty ? 'text.disabled' : color}
        component="span"
      >
        {label && (
          <Box component="span" sx={{ fontWeight: 500 }}>
            {label}:{' '}
          </Box>
        )}
        <Box 
          component="span" 
          className="info-value"
          sx={{ 
            color: isEmpty ? 'text.disabled' : (valueColor || 'text.primary'),
            fontWeight: label ? 400 : 500
          }}
        >
          {displayValue}
        </Box>
      </Typography>
    </Stack>
  );

  // Wrap with tooltip if provided
  if (tooltip) {
    return (
      <Tooltip title={tooltip} arrow>
        {content}
      </Tooltip>
    );
  }

  return content;
}

InfoItem.propTypes = {
  /** Icon component from ant-design/icons */
  icon: PropTypes.elementType,
  /** Label text (optional, displayed before value) */
  label: PropTypes.string,
  /** Value to display */
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.node]),
  /** Color for label and icon */
  color: PropTypes.string,
  /** Color for the value specifically */
  valueColor: PropTypes.string,
  /** Click handler (makes item clickable) */
  onClick: PropTypes.func,
  /** Tooltip text */
  tooltip: PropTypes.string,
  /** Size variant */
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  /** Text to display when value is empty */
  emptyText: PropTypes.string,
  /** Additional styles */
  sx: PropTypes.object
};