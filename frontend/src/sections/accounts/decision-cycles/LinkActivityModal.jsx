// frontend/src/sections/accounts/decision-cycles/LinkActivityModal.jsx
/**
 * Link Activity Modal Component
 * 
 * Modal for linking existing activities to a decision step.
 * Displays unlinked activities for the account and allows selection.
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect, useMemo, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';

// ant-design icons
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import LinkOutlined from '@ant-design/icons/LinkOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import SearchOutlined from '@ant-design/icons/SearchOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import InboxOutlined from '@ant-design/icons/InboxOutlined';

// project imports
import MainCard from 'components/MainCard';
import { 
  getUnlinkedActivities, 
  linkActivityToStep,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS
} from 'api/accounts/activities';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| CONSTANTS ||============================== //

const ACTIVITY_TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: MailOutlined,
  OTHER: CalendarOutlined
};

// ==============================|| ACTIVITY LIST ITEM ||============================== //

function ActivityListItem({ activity, selected, onToggle }) {
  const theme = useTheme();
  const TypeIcon = ACTIVITY_TYPE_ICONS[activity.activity_type] || CalendarOutlined;
  
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <ListItem disablePadding>
      <ListItemButton
        onClick={() => onToggle(activity.id)}
        selected={selected}
        sx={{
          borderRadius: 1,
          mb: 0.5,
          border: '1px solid',
          borderColor: selected ? 'primary.main' : 'divider',
          bgcolor: selected ? alpha(theme.palette.primary.main, 0.08) : 'background.paper',
          '&:hover': {
            borderColor: 'primary.light',
            bgcolor: alpha(theme.palette.primary.main, 0.04)
          }
        }}
      >
        <ListItemIcon sx={{ minWidth: 40 }}>
          <Checkbox
            edge="start"
            checked={selected}
            disableRipple
            size="small"
          />
        </ListItemIcon>
        
        <ListItemIcon sx={{ minWidth: 36 }}>
          <Box
            sx={{
              p: 0.75,
              borderRadius: 1,
              bgcolor: 'grey.100',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <TypeIcon style={{ fontSize: 16, color: theme.palette.text.secondary }} />
          </Box>
        </ListItemIcon>
        
        <ListItemText
          primary={
            <Stack direction="row" alignItems="center" spacing={1}>
              <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1 }}>
                {activity.title}
              </Typography>
              <Chip
                label={ACTIVITY_STATUS_LABELS[activity.status] || activity.status}
                size="small"
                color={ACTIVITY_STATUS_COLORS[activity.status] || 'default'}
                variant="outlined"
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
            </Stack>
          }
          secondary={
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 0.25 }}>
              <Typography variant="caption" color="text.secondary">
                {ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type}
              </Typography>
              {activity.scheduled_date && (
                <>
                  <Typography variant="caption" color="text.disabled">•</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatDate(activity.scheduled_date)}
                  </Typography>
                </>
              )}
              {activity.owner_name && (
                <>
                  <Typography variant="caption" color="text.disabled">•</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {activity.owner_name}
                  </Typography>
                </>
              )}
            </Stack>
          }
          primaryTypographyProps={{ component: 'div' }}
          secondaryTypographyProps={{ component: 'div' }}
        />
      </ListItemButton>
    </ListItem>
  );
}

ActivityListItem.propTypes = {
  activity: PropTypes.object.isRequired,
  selected: PropTypes.bool.isRequired,
  onToggle: PropTypes.func.isRequired
};

// ==============================|| EMPTY STATE ||============================== //

function EmptyState({ searchQuery }) {
  return (
    <Box
      sx={{
        py: 6,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      <InboxOutlined style={{ fontSize: 48, color: '#bfbfbf' }} />
      <Typography variant="body1" color="text.secondary" sx={{ mt: 2 }}>
        {searchQuery 
          ? 'No activities match your search'
          : 'No unlinked activities found'
        }
      </Typography>
      <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5 }}>
        {searchQuery
          ? 'Try a different search term'
          : 'All activities are already linked to steps'
        }
      </Typography>
    </Box>
  );
}

EmptyState.propTypes = {
  searchQuery: PropTypes.string
};

// ==============================|| LINK ACTIVITY MODAL ||============================== //

/**
 * LinkActivityModal Component
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} onClose - Close modal callback
 * @param {string} accountId - Account UUID to fetch activities for
 * @param {string} cycleId - Decision Cycle UUID to link to
 * @param {Object} step - Decision Step object to link activities to
 * @param {Function} onSuccess - Success callback after linking
 */
export default function LinkActivityModal({
  open,
  onClose,
  accountId,
  cycleId,
  step,
  onSuccess
}) {
  const theme = useTheme();
  
  // State
  const [loading, setLoading] = useState(false);
  const [linking, setLinking] = useState(false);
  const [activities, setActivities] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState(null);

  // Load unlinked activities when modal opens
  useEffect(() => {
    if (open && accountId) {
      loadActivities();
    }
    // Reset state when modal closes
    if (!open) {
      setSelectedIds([]);
      setSearchQuery('');
      setError(null);
    }
  }, [open, accountId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadActivities = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await getUnlinkedActivities(accountId, { limit: 100 });
      
      if (result.success) {
        setActivities(result.data || []);
      } else {
        setError(result.error || 'Failed to load activities');
      }
    } catch (err) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Filter activities by search query
  const filteredActivities = useMemo(() => {
    if (!searchQuery.trim()) return activities;
    
    const query = searchQuery.toLowerCase();
    return activities.filter(activity => 
      activity.title?.toLowerCase().includes(query) ||
      activity.activity_type?.toLowerCase().includes(query) ||
      activity.owner_name?.toLowerCase().includes(query)
    );
  }, [activities, searchQuery]);

  // Handle selection toggle
  const handleToggle = useCallback((activityId) => {
    setSelectedIds(prev => {
      if (prev.includes(activityId)) {
        return prev.filter(id => id !== activityId);
      }
      return [...prev, activityId];
    });
  }, []);

  // Handle select all
  const handleSelectAll = useCallback(() => {
    if (selectedIds.length === filteredActivities.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredActivities.map(a => a.id));
    }
  }, [selectedIds.length, filteredActivities]);

  // Handle link activities
  const handleLink = async () => {
    if (selectedIds.length === 0 || !cycleId || !step?.id) return;
    
    setLinking(true);
    
    try {
      // Link each selected activity
      const results = await Promise.all(
        selectedIds.map(activityId => 
          linkActivityToStep(activityId, cycleId, step.id, accountId)
        )
      );
      
      const successCount = results.filter(r => r.success).length;
      const failCount = results.filter(r => !r.success).length;
      
      if (successCount > 0) {
        displaySuccessSnackbar(
          `${successCount} activit${successCount === 1 ? 'y' : 'ies'} linked to ${step.name}`
        );
        onSuccess?.(results.filter(r => r.success).map(r => r.data));
        onClose();
      }
      
      if (failCount > 0 && successCount === 0) {
        displayErrorSnackbar(`Failed to link ${failCount} activit${failCount === 1 ? 'y' : 'ies'}`);
      }
    } catch (err) {
      displayErrorSnackbar(err.message || 'An error occurred');
    } finally {
      setLinking(false);
    }
  };

  const handleClose = () => {
    if (!linking) {
      onClose();
    }
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="modal-link-activity-title"
      sx={{
        '& .MuiPaper-root:focus': { outline: 'none' }
      }}
    >
      <MainCard
        sx={{
          width: 'calc(100% - 48px)',
          minWidth: 400,
          maxWidth: 600,
          maxHeight: 'calc(100vh - 48px)',
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          display: 'flex',
          flexDirection: 'column'
        }}
        modal
        content={false}
      >
        {/* Header */}
        <Box sx={{ p: 2.5, pb: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <LinkOutlined style={{ fontSize: 24, color: theme.palette.primary.main }} />
              <Box>
                <Typography variant="h5" id="modal-link-activity-title">
                  Link Existing Activities
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  to {step?.name || 'Step'}
                </Typography>
              </Box>
            </Stack>
            <IconButton size="small" onClick={handleClose} disabled={linking}>
              <CloseOutlined />
            </IconButton>
          </Stack>
        </Box>
        
        <Divider />
        
        {/* Search */}
        <Box sx={{ px: 2.5, py: 1.5 }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search activities..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchOutlined style={{ fontSize: 16, color: theme.palette.text.disabled }} />
                </InputAdornment>
              )
            }}
          />
        </Box>
        
        {/* Select All */}
        {!loading && filteredActivities.length > 0 && (
          <Box sx={{ px: 2.5, pb: 1 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Button
                size="small"
                onClick={handleSelectAll}
                sx={{ textTransform: 'none' }}
              >
                {selectedIds.length === filteredActivities.length ? 'Deselect All' : 'Select All'}
              </Button>
              <Typography variant="caption" color="text.secondary">
                {selectedIds.length} of {filteredActivities.length} selected
              </Typography>
            </Stack>
          </Box>
        )}
        
        <Divider />
        
        {/* Activity List */}
        <Box 
          sx={{ 
            flex: 1, 
            overflow: 'auto', 
            px: 2.5, 
            py: 1.5,
            minHeight: 200,
            maxHeight: 400
          }}
        >
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress size={32} />
            </Box>
          ) : error ? (
            <Box sx={{ py: 4, textAlign: 'center' }}>
              <Typography color="error">{error}</Typography>
              <Button size="small" onClick={loadActivities} sx={{ mt: 1 }}>
                Retry
              </Button>
            </Box>
          ) : filteredActivities.length === 0 ? (
            <EmptyState searchQuery={searchQuery} />
          ) : (
            <List disablePadding>
              {filteredActivities.map((activity) => (
                <ActivityListItem
                  key={activity.id}
                  activity={activity}
                  selected={selectedIds.includes(activity.id)}
                  onToggle={handleToggle}
                />
              ))}
            </List>
          )}
        </Box>
        
        <Divider />
        
        {/* Actions */}
        <Box sx={{ p: 2.5 }}>
          <Stack direction="row" spacing={2} justifyContent="flex-end">
            <Button 
              color="inherit" 
              onClick={handleClose}
              disabled={linking}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleLink}
              disabled={linking || selectedIds.length === 0}
              startIcon={
                linking 
                  ? <CircularProgress size={16} color="inherit" /> 
                  : <CheckCircleOutlined />
              }
            >
              {linking 
                ? 'Linking...' 
                : `Link ${selectedIds.length} Activit${selectedIds.length === 1 ? 'y' : 'ies'}`
              }
            </Button>
          </Stack>
        </Box>
      </MainCard>
    </Modal>
  );
}

// ==============================|| PROP TYPES ||============================== //

LinkActivityModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  accountId: PropTypes.string,
  cycleId: PropTypes.string,
  step: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string
  }),
  onSuccess: PropTypes.func
};