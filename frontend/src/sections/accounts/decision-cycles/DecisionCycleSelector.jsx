// frontend/src/sections/accounts/decision-cycles/DecisionCycleSelector.jsx
/**
 * Decision Cycle Selector Component
 * 
 * Dropdown selector for choosing active decision cycle.
 * Displayed at the top of the Decision Cycle tab.
 * 
 * Features:
 * - Display current cycle name
 * - Dropdown to switch between cycles
 * - Create new cycle option
 * - Rename/Delete actions on hover
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';

// icons
import DownOutlined from '@ant-design/icons/DownOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';
import FolderOutlined from '@ant-design/icons/FolderOutlined';

// project imports
import {
  CYCLE_DERIVED_STATUS_LABELS,
  CYCLE_STATUS_COLORS
} from 'api/accounts/decisionCycles';

// ==============================|| CYCLE MENU ITEM ||============================== //

function CycleMenuItem({ cycle, isSelected, onSelect, onEdit, onDelete }) {
  const theme = useTheme();
  const [isHovered, setIsHovered] = useState(false);
  
  return (
    <MenuItem
      selected={isSelected}
      onClick={() => onSelect(cycle)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{
        py: 1,
        px: 2,
        minWidth: 280
      }}
    >
      <ListItemIcon sx={{ minWidth: 32 }}>
        {isSelected ? (
          <CheckCircleFilled style={{ color: theme.palette.primary.main }} />
        ) : (
          <FolderOutlined style={{ color: theme.palette.text.secondary }} />
        )}
      </ListItemIcon>
      
      <ListItemText
        primary={
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body1" fontWeight={isSelected ? 600 : 400}>
              {cycle.name}
            </Typography>
            {cycle.cycle_status && (
              <Chip
                label={CYCLE_DERIVED_STATUS_LABELS[cycle.cycle_status] || cycle.cycle_status}
                color={CYCLE_STATUS_COLORS[cycle.cycle_status] || 'default'}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.65rem', '& .MuiChip-label': { px: 0.75 } }}
              />
            )}
          </Stack>
        }
        secondary={
          cycle.steps_count !== undefined
            ? `${cycle.validated_steps_count || 0}/${cycle.steps_count} validated`
            : null
        }
        primaryTypographyProps={{ component: 'div' }}
        secondaryTypographyProps={{
          variant: 'caption'
        }}
      />
      
      {/* Actions on hover */}
      {isHovered && (
        <Stack direction="row" spacing={0}>
          <Tooltip title="Rename">
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onEdit(cycle);
              }}
              sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
            >
              <EditOutlined style={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(cycle);
              }}
              sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
            >
              <DeleteOutlined style={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      )}
    </MenuItem>
  );
}

CycleMenuItem.propTypes = {
  cycle: PropTypes.object.isRequired,
  isSelected: PropTypes.bool,
  onSelect: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired
};

// ==============================|| DECISION CYCLE SELECTOR ||============================== //

/**
 * DecisionCycleSelector Component
 * 
 * @param {Array} cycles - List of available cycles
 * @param {Object} currentCycle - Currently selected cycle
 * @param {Function} onCycleChange - Callback when cycle is changed
 * @param {Function} onCreateCycle - Callback to create new cycle
 * @param {Function} onEditCycle - Callback to edit cycle (rename)
 * @param {Function} onDeleteCycle - Callback to delete cycle
 * @param {boolean} loading - Loading state
 */
export default function DecisionCycleSelector({
  cycles = [],
  currentCycle,
  onCycleChange,
  onCreateCycle,
  onEditCycle,
  onDeleteCycle,
  loading = false
}) {
  const theme = useTheme();
  
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);
  
  // ==============================|| HANDLERS ||============================== //
  
  const handleClick = useCallback((event) => {
    setAnchorEl(event.currentTarget);
  }, []);
  
  const handleClose = useCallback(() => {
    setAnchorEl(null);
  }, []);
  
  const handleSelectCycle = useCallback((cycle) => {
    onCycleChange?.(cycle);
    handleClose();
  }, [onCycleChange, handleClose]);
  
  const handleCreateCycle = useCallback(() => {
    onCreateCycle?.();
    handleClose();
  }, [onCreateCycle, handleClose]);
  
  const handleEditCycle = useCallback((cycle) => {
    onEditCycle?.(cycle);
    handleClose();
  }, [onEditCycle, handleClose]);
  
  const handleDeleteCycle = useCallback((cycle) => {
    onDeleteCycle?.(cycle);
    handleClose();
  }, [onDeleteCycle, handleClose]);
  
  // ==============================|| RENDER - LOADING ||============================== //
  
  if (loading) {
    return (
      <Stack direction="row" spacing={2} alignItems="center">
        <Skeleton variant="rounded" width={200} height={40} />
      </Stack>
    );
  }
  
  // ==============================|| RENDER - NO CYCLES ||============================== //
  
  if (!cycles || cycles.length === 0) {
    return (
      <Button
        variant="outlined"
        startIcon={<PlusOutlined />}
        onClick={onCreateCycle}
        sx={{
          borderStyle: 'dashed'
        }}
      >
        Create Decision Cycle
      </Button>
    );
  }
  
  // ==============================|| RENDER ||============================== //
  
  return (
    <Box>
      {/* Selector Button */}
      <Button
        variant="outlined"
        onClick={handleClick}
        endIcon={<DownOutlined style={{ fontSize: 12 }} />}
        sx={{
          minWidth: 200,
          justifyContent: 'space-between',
          textTransform: 'none',
          fontWeight: 600,
          px: 2,
          py: 1,
          bgcolor: open ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
          borderColor: open ? 'primary.main' : 'divider',
          '&:hover': {
            bgcolor: alpha(theme.palette.primary.main, 0.08),
            borderColor: 'primary.main'
          }
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <FolderOutlined style={{ fontSize: 16 }} />
          <Typography variant="body2" fontWeight={600}>
            {currentCycle?.name || 'Select Cycle'}
          </Typography>
        </Stack>
      </Button>
      
      {/* Dropdown Menu */}
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left'
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left'
        }}
        PaperProps={{
          sx: {
            mt: 0.5,
            minWidth: 280,
            maxHeight: 400,
            boxShadow: theme.shadows[8]
          }
        }}
      >
        {/* Cycles List */}
        {cycles.map((cycle) => (
          <CycleMenuItem
            key={cycle.id}
            cycle={cycle}
            isSelected={currentCycle?.id === cycle.id}
            onSelect={handleSelectCycle}
            onEdit={handleEditCycle}
            onDelete={handleDeleteCycle}
          />
        ))}
        
        <Divider sx={{ my: 1 }} />
        
        {/* Create New Cycle */}
        <MenuItem onClick={handleCreateCycle}>
          <ListItemIcon sx={{ minWidth: 32 }}>
            <PlusOutlined style={{ color: theme.palette.primary.main }} />
          </ListItemIcon>
          <ListItemText
            primary="Create New Cycle"
            primaryTypographyProps={{
              color: 'primary',
              fontWeight: 500
            }}
          />
        </MenuItem>
      </Menu>
    </Box>
  );
}

DecisionCycleSelector.propTypes = {
  cycles: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      steps_count: PropTypes.number,
      is_active: PropTypes.bool
    })
  ),
  currentCycle: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string
  }),
  onCycleChange: PropTypes.func,
  onCreateCycle: PropTypes.func,
  onEditCycle: PropTypes.func,
  onDeleteCycle: PropTypes.func,
  loading: PropTypes.bool
};