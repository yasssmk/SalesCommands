// frontend/src/components/cards/RemovableCard.jsx
/**
 * RemovableCard Component
 * 
 * A card wrapper with hover-reveal remove button.
 * Used for displaying items that can be removed from a list.
 * 
 * Used in:
 * - Activity Overview (contacts, users)
 * - Decision Step (contacts)
 * - Any list of removable items
 */

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// MUI
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import { alpha, useTheme } from '@mui/material/styles';

// Icons
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// ==============================|| REMOVABLE CARD ||============================== //

export default function RemovableCard({
  children,
  onRemove,
  removeTooltip = 'Remove',
  removable = true,
  variant = 'default',
  selected = false,
  onClick,
  sx = {}
}) {
  const theme = useTheme();
  const [hovered, setHovered] = useState(false);

  // Variant styles
  const variantStyles = {
    default: {
      bgcolor: 'grey.50',
      border: '1px solid',
      borderColor: selected ? 'primary.main' : 'grey.200',
      '&:hover': { 
        borderColor: selected ? 'primary.main' : 'grey.300' 
      }
    },
    outlined: {
      bgcolor: 'background.paper',
      border: '1px solid',
      borderColor: selected ? 'primary.main' : 'divider',
      '&:hover': { 
        borderColor: selected ? 'primary.main' : 'primary.light',
        bgcolor: alpha(theme.palette.primary.main, 0.02)
      }
    },
    filled: {
      bgcolor: selected ? alpha(theme.palette.primary.main, 0.08) : 'grey.100',
      border: 'none',
      '&:hover': { 
        bgcolor: selected 
          ? alpha(theme.palette.primary.main, 0.12) 
          : 'grey.200' 
      }
    }
  };

  return (
    <Box
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onClick}
      sx={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        p: 1.5,
        borderRadius: 1,
        transition: 'all 0.2s ease',
        cursor: onClick ? 'pointer' : 'default',
        ...variantStyles[variant],
        ...sx
      }}
    >
      {children}
      
      {/* Remove button - shows on hover */}
      {removable && onRemove && hovered && (
        <Tooltip title={removeTooltip}>
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            sx={{
              position: 'absolute',
              top: 4,
              right: 4,
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
  );
}

RemovableCard.propTypes = {
  /** Card content */
  children: PropTypes.node.isRequired,
  /** Callback when remove button is clicked */
  onRemove: PropTypes.func,
  /** Tooltip text for remove button */
  removeTooltip: PropTypes.string,
  /** Whether the card can be removed (shows remove button on hover) */
  removable: PropTypes.bool,
  /** Visual variant of the card */
  variant: PropTypes.oneOf(['default', 'outlined', 'filled']),
  /** Whether the card is selected */
  selected: PropTypes.bool,
  /** Callback when card is clicked */
  onClick: PropTypes.func,
  /** Additional styles */
  sx: PropTypes.object
};