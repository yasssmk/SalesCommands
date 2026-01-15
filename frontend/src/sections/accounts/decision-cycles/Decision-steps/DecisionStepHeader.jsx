// frontend/src/sections/accounts/decision-cycles/DecisionStepHeader.jsx

'use client';

import { useState } from 'react';
import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// MUI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import Tooltip from '@mui/material/Tooltip';

// Project imports
import MainCard from 'components/MainCard';
import { 
  updateDecisionStepStatus,
  deleteDecisionStep,
  STATUS_COLORS,
  STEP_TYPE_LABELS
} from 'api/accounts/decisionCycles';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';
import AlertStepDelete from 'sections/accounts/decision-cycles/AlertStepDelete';

// Icons
import {
  EditOutlined,
  CheckOutlined,
  CloseOutlined,
  MoreOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  PhoneOutlined,
  MailOutlined,
  TeamOutlined,
  CheckSquareOutlined,
  AuditOutlined,
  SafetyOutlined,
  QuestionCircleOutlined
} from '@ant-design/icons';

// Date formatting
import { format } from 'date-fns';

// ==============================|| CONFIGURATION ||============================== //

const STATUS_CONFIG = {
  NOT_STARTED: { color: 'default', label: 'Not Started' },
  PENDING_CLIENT: { color: 'warning', label: 'Pending Client' },
  IN_PROGRESS: { color: 'info', label: 'In Progress' },
  IN_CHASING: { color: 'secondary', label: 'In Chasing' },
  VALIDATED: { color: 'success', label: 'Validated' },
  REJECTED: { color: 'error', label: 'Rejected' }
};

const STAGE_LABELS = {
  EXPLORATION: 'Exploration',
  CRITERIA_VALIDATION: 'Criteria Validation',
  SOLUTION_CONFIRMATION: 'Solution Confirmation',
  BUSINESS_VALIDATION: 'Business Validation',
  FORMALIZATION: 'Formalization'
};

// Step type icons mapping
const TYPE_ICONS = {
  MEETING: TeamOutlined,
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  TASK_SELLER: CheckSquareOutlined,
  TASK_BUYER: AuditOutlined,
  INTERNAL_VALIDATION: SafetyOutlined,
  OTHER: QuestionCircleOutlined
};

// ==============================|| STEP HEADER ||============================== //

export default function StepHeader({ step, account, cycleId, onSave, onUpdate }) {
  const router = useRouter();

  // Edit name state
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState(step?.name || '');
  const [saving, setSaving] = useState(false);

  // Menu state
  const [anchorEl, setAnchorEl] = useState(null);
  const menuOpen = Boolean(anchorEl);

  // Delete dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Status menu state
  const [statusAnchorEl, setStatusAnchorEl] = useState(null);
  const statusMenuOpen = Boolean(statusAnchorEl);

  // Get type icon component
  const TypeIcon = TYPE_ICONS[step?.step_type] || TYPE_ICONS.OTHER;
  const statusConfig = STATUS_CONFIG[step?.status] || STATUS_CONFIG.NOT_STARTED;

  // ==============================|| HANDLERS ||============================== //

  // Handle name save
  const handleNameSave = async () => {
    if (nameValue === step?.name) {
      setEditingName(false);
      return;
    }
    setSaving(true);
    const success = await onSave('name', nameValue);
    setSaving(false);
    if (success) {
      setEditingName(false);
    }
  };

  // Handle name cancel
  const handleNameCancel = () => {
    setNameValue(step?.name || '');
    setEditingName(false);
  };

  // Handle menu
  const handleMenuOpen = (event) => setAnchorEl(event.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  // Handle status menu
  const handleStatusMenuOpen = (event) => setStatusAnchorEl(event.currentTarget);
  const handleStatusMenuClose = () => setStatusAnchorEl(null);

  // Handle status change
  const handleStatusChange = async (newStatus) => {
    handleStatusMenuClose();
    setSaving(true);
    
    try {
      const result = await updateDecisionStepStatus(step.id, newStatus, cycleId);
      if (result.success) {
        displaySuccessSnackbar('Status updated');
        onUpdate?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to update status');
      }
    } catch (error) {
      displayErrorSnackbar('An error occurred');
    } finally {
      setSaving(false);
    }
  };

  // Handle mark as validated (quick action)
  const handleMarkValidated = () => {
    handleStatusChange('VALIDATED');
  };

  // Handle delete
  const handleDeleteClick = () => {
    handleMenuClose();
    setDeleteDialogOpen(true);
  };

  const handleDeleteSuccess = () => {
    setDeleteDialogOpen(false);
    // Navigate back to account after deletion
    if (account?.id) {
      router.push(`/accounts/${account.id}?tab=decision-cycle`);
    } else {
      router.back();
    }
  };

  // Format scheduled date
  const formatScheduledDate = () => {
    if (!step?.scheduled_date) return 'Not scheduled';
    const dateStr = format(new Date(step.scheduled_date), 'MMM d, yyyy');
    if (step?.scheduled_time) {
      return `${dateStr} at ${step.scheduled_time.slice(0, 5)}`;
    }
    return dateStr;
  };

  // Determine if step can be validated
  const canValidate = step?.status !== 'VALIDATED' && step?.status !== 'REJECTED';

  return (
    <>
      <MainCard sx={{ mb: 0, borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}>
        <Stack spacing={2}>
          {/* Row 1: Title + Status/Stage chips */}
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Stack direction="row" spacing={2} alignItems="center" flex={1}>
              {/* Type Icon */}
              {TypeIcon && (
                <Tooltip title={STEP_TYPE_LABELS[step?.step_type] || 'Step'}>
                  <Box sx={{ fontSize: 24, color: 'primary.main', display: 'flex', alignItems: 'center' }}>
                    <TypeIcon />
                  </Box>
                </Tooltip>
              )}

              {/* Name - Inline Editable */}
              {editingName ? (
                <Stack direction="row" spacing={1} alignItems="center" flex={1}>
                  <TextField
                    value={nameValue}
                    onChange={(e) => setNameValue(e.target.value)}
                    size="small"
                    fullWidth
                    autoFocus
                    disabled={saving}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleNameSave();
                      if (e.key === 'Escape') handleNameCancel();
                    }}
                  />
                  <IconButton size="small" onClick={handleNameSave} disabled={saving} color="success">
                    <CheckOutlined />
                  </IconButton>
                  <IconButton size="small" onClick={handleNameCancel} disabled={saving} color="error">
                    <CloseOutlined />
                  </IconButton>
                </Stack>
              ) : (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="h4">{step?.name}</Typography>
                  <IconButton size="small" onClick={() => setEditingName(true)}>
                    <EditOutlined />
                  </IconButton>
                </Stack>
              )}
            </Stack>

            {/* Status + Stage Chips */}
            <Stack direction="row" spacing={1} alignItems="center">
              {/* Stage Chip (fixed) */}
              <Chip
                label={STAGE_LABELS[step?.stage] || step?.stage}
                size="small"
                variant="outlined"
              />
              
              {/* Status Chip (clickable to change) */}
              <Tooltip title="Click to change status">
                <Chip
                  label={statusConfig.label}
                  color={statusConfig.color}
                  size="small"
                  onClick={handleStatusMenuOpen}
                  sx={{ cursor: 'pointer' }}
                />
              </Tooltip>
              
              {/* Status Menu */}
              <Menu
                anchorEl={statusAnchorEl}
                open={statusMenuOpen}
                onClose={handleStatusMenuClose}
              >
                {Object.entries(STATUS_CONFIG).map(([key, config]) => (
                  <MenuItem
                    key={key}
                    onClick={() => handleStatusChange(key)}
                    selected={step?.status === key}
                  >
                    <Chip
                      label={config.label}
                      color={config.color}
                      size="small"
                      variant={step?.status === key ? 'filled' : 'outlined'}
                      sx={{ pointerEvents: 'none' }}
                    />
                  </MenuItem>
                ))}
              </Menu>
            </Stack>
          </Stack>

          {/* Row 2: Meta info + Actions */}
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            {/* Meta info */}
            <Stack direction="row" spacing={2} divider={<Divider orientation="vertical" flexItem />}>
              <Typography variant="body2" color="text.secondary">
                <strong>Account:</strong> {account?.company_name || '-'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Type:</strong> {STEP_TYPE_LABELS[step?.step_type] || '-'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Scheduled:</strong> {formatScheduledDate()}
              </Typography>
              {step?.stakeholder && (
                <Typography variant="body2" color="text.secondary">
                  <strong>Stakeholder:</strong> {step.stakeholder}
                </Typography>
              )}
            </Stack>

            {/* Actions */}
            <Stack direction="row" spacing={1}>
              {canValidate && (
                <Button
                  variant="contained"
                  color="success"
                  size="small"
                  startIcon={<CheckCircleOutlined />}
                  onClick={handleMarkValidated}
                  disabled={saving}
                >
                  Mark Validated
                </Button>
              )}
              <IconButton onClick={handleMenuOpen}>
                <MoreOutlined />
              </IconButton>
              <Menu anchorEl={anchorEl} open={menuOpen} onClose={handleMenuClose}>
                <MenuItem onClick={handleDeleteClick} sx={{ color: 'error.main' }}>
                  <DeleteOutlined style={{ marginRight: 8 }} />
                  Delete Step
                </MenuItem>
              </Menu>
            </Stack>
          </Stack>
        </Stack>
      </MainCard>

      {/* Delete Dialog */}
      <AlertStepDelete
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        step={step}
        cycleId={cycleId}
        onSuccess={handleDeleteSuccess}
      />
    </>
  );
}

StepHeader.propTypes = {
  step: PropTypes.object.isRequired,
  account: PropTypes.object,
  cycleId: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};
