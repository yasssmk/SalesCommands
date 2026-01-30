// frontend/src/sections/activities/workspace/LinkExistingActivityModal.jsx
/**
 * Link Existing Activity Modal
 * 
 * Allows linking an existing activity as the "next step" of the current activity.
 * Shows activities from the same account that are not completed/cancelled.
 */

'use client';

import { useState, useMemo } from 'react';
import PropTypes from 'prop-types';

// MUI
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import InputAdornment from '@mui/material/InputAdornment';

// Icons
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import SearchOutlined from '@ant-design/icons/SearchOutlined';
import CheckOutlined from '@ant-design/icons/CheckOutlined';

// Project imports
import {
  useGetActivitiesByAccount,
  updateActivity,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS
} from 'api/accounts/activities';
import { displayErrorSnackbar } from 'utils/displayError';

// ==============================|| ACTIVITY LIST ITEM ||============================== //

function ActivityListItem({ activity, selected, onSelect }) {
  const theme = useTheme();

  return (
    <ListItemButton
      selected={selected}
      onClick={() => onSelect(activity)}
      sx={{
        borderRadius: 1,
        mb: 0.5,
        border: '1px solid',
        borderColor: selected ? 'primary.main' : 'divider',
        bgcolor: selected ? 'primary.lighter' : 'background.paper',
        '&:hover': {
          bgcolor: selected ? 'primary.lighter' : 'action.hover'
        }
      }}
    >
      <Stack direction="row" spacing={2} alignItems="center" sx={{ width: '100%' }}>
        {/* Type chip */}
        <Chip
          label={ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type}
          size="small"
          variant="outlined"
          sx={{ minWidth: 80 }}
        />
        
        {/* Title & Date */}
        <Stack sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" fontWeight={500} noWrap>
            {activity.title}
          </Typography>
          {activity.scheduled_date && (
            <Typography variant="caption" color="text.secondary">
              {new Date(activity.scheduled_date).toLocaleDateString()}
              {activity.scheduled_time && ` at ${activity.scheduled_time.slice(0, 5)}`}
            </Typography>
          )}
        </Stack>
        
        {/* Status chip */}
        <Chip
          label={ACTIVITY_STATUS_LABELS[activity.status] || activity.status}
          size="small"
          color={ACTIVITY_STATUS_COLORS[activity.status] || 'default'}
        />
        
        {/* Selected indicator */}
        {selected && (
          <CheckOutlined 
            style={{ 
              color: theme.palette.primary.main, 
              fontSize: theme.iconSizes.lg 
            }} 
          />
        )}
      </Stack>
    </ListItemButton>
  );
}

ActivityListItem.propTypes = {
  activity: PropTypes.object.isRequired,
  selected: PropTypes.bool,
  onSelect: PropTypes.func.isRequired
};

// ==============================|| LINK EXISTING ACTIVITY MODAL ||============================== //

/**
 * LinkExistingActivityModal Component
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} onClose - Close modal callback
 * @param {Object} currentActivity - The current activity to link FROM
 * @param {Function} onSuccess - Success callback after linking
 */
export default function LinkExistingActivityModal({
  open,
  onClose,
  currentActivity,
  onSuccess
}) {
  const [selectedActivity, setSelectedActivity] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [linking, setLinking] = useState(false);

  // Fetch activities for the same account
  const accountId = currentActivity?.account;
  const {
    activities,
    activitiesLoading,
    activitiesEmpty
  } = useGetActivitiesByAccount(accountId, {
    pageSize: 100,
    ordering: '-scheduled_date'
  });

  // Filter activities:
  // - Exclude current activity
  // - Exclude completed/cancelled
  // - Exclude activities that already have a previous_activity (already linked)
  // - Apply search filter
  const filteredActivities = useMemo(() => {
    if (!activities) return [];
    
    return activities.filter(activity => {
      // Exclude current activity
      if (activity.id === currentActivity?.id) return false;
      
      // Exclude completed/cancelled
      if (['COMPLETED', 'CANCELLED'].includes(activity.status)) return false;
      
      // Exclude if already has a previous activity (already part of a chain)
      if (activity.previous_activity) return false;
      
      // Apply search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesTitle = activity.title?.toLowerCase().includes(query);
        const matchesType = ACTIVITY_TYPE_LABELS[activity.activity_type]?.toLowerCase().includes(query);
        return matchesTitle || matchesType;
      }
      
      return true;
    });
  }, [activities, currentActivity?.id, searchQuery]);

  // Handle activity selection
  const handleSelect = (activity) => {
    setSelectedActivity(prev => 
      prev?.id === activity.id ? null : activity
    );
  };

  // Handle link action
  const handleLink = async () => {
    if (!selectedActivity || !currentActivity?.id) return;

    setLinking(true);
    try {
      // Update current activity to set next_activity
      const result = await updateActivity(currentActivity.id, {
        next_activity_id: selectedActivity.id
      });

      if (result.success) {
        onSuccess?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to link activity');
      }
    } catch (error) {
      displayErrorSnackbar('An error occurred while linking');
    } finally {
      setLinking(false);
    }
  };

  // Handle close - reset state
  const handleClose = () => {
    setSelectedActivity(null);
    setSearchQuery('');
    onClose();
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose} 
      maxWidth="sm" 
      fullWidth
      PaperProps={{ sx: { maxHeight: '80vh' } }}
    >
      <DialogTitle>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h5">Link Existing Activity</Typography>
          <IconButton size="small" onClick={handleClose}>
            <CloseOutlined />
          </IconButton>
        </Stack>
      </DialogTitle>

      <DialogContent dividers>
        {/* Search field */}
        <TextField
          fullWidth
          size="small"
          placeholder="Search activities..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlined />
              </InputAdornment>
            )
          }}
          sx={{ mb: 2 }}
        />

        {/* Loading state */}
        {activitiesLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={32} />
          </Box>
        )}

        {/* Empty state */}
        {!activitiesLoading && filteredActivities.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="text.secondary">
              {activitiesEmpty 
                ? 'No activities found for this account'
                : searchQuery 
                  ? 'No activities match your search'
                  : 'No available activities to link'
              }
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Only planned or in-progress activities can be linked as next steps.
            </Typography>
          </Box>
        )}

        {/* Activity list */}
        {!activitiesLoading && filteredActivities.length > 0 && (
          <List sx={{ py: 0 }}>
            {filteredActivities.map((activity) => (
              <ActivityListItem
                key={activity.id}
                activity={activity}
                selected={selectedActivity?.id === activity.id}
                onSelect={handleSelect}
              />
            ))}
          </List>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose} disabled={linking}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleLink}
          disabled={!selectedActivity || linking}
        >
          {linking ? 'Linking...' : 'Link as Next Step'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

LinkExistingActivityModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  currentActivity: PropTypes.object,
  onSuccess: PropTypes.func
};