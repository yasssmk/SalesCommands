import PropTypes from 'prop-types';
import { useRef, useState } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
import Badge from '@mui/material/Badge';
import Box from '@mui/material/Box';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Paper from '@mui/material/Paper';
import Popper from '@mui/material/Popper';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// project import
import MainCard from 'components/MainCard';
import Transitions from 'components/@extended/Transitions';
import IconButton from 'components/@extended/IconButton';
import { ThemeMode } from 'config';
import { displayErrorSnackbar } from 'utils/displayError';
import {
  useGetNotifications,
  useUnreadCount,
  markNotificationRead,
} from 'api/notifications/notifications';

// assets
import BellOutlined from '@ant-design/icons/BellOutlined';

// ==============================|| HEADER CONTENT - NOTIFICATION ||============================== //

export default function Notification() {
  const theme = useTheme();

  const anchorRef = useRef(null);
  const [open, setOpen] = useState(false);

  const { unreadCount, mutateUnreadCount } = useUnreadCount();
  // The list is only fetched while the dropdown is open (no polling).
  const { notifications, mutateNotifications } = useGetNotifications({ enabled: open });

  const handleToggle = () => {
    setOpen((prevOpen) => !prevOpen);
  };

  const handleClose = (event) => {
    if (anchorRef.current && anchorRef.current.contains(event.target)) {
      return;
    }
    setOpen(false);
  };

  const handleRead = async (notificationId) => {
    const result = await markNotificationRead(notificationId);
    if (!result.success) {
      displayErrorSnackbar(result);
      return;
    }
    // Refresh both the unread badge and the open list.
    mutateUnreadCount();
    mutateNotifications();
  };

  const iconBackColorOpen = theme.palette.mode === ThemeMode.DARK ? 'background.default' : 'grey.100';

  return (
    <Box sx={{ flexShrink: 0, ml: 0.75 }}>
      <Tooltip title="Notifications">
        <IconButton
          color="secondary"
          variant="light"
          sx={{ color: 'text.primary', bgcolor: open ? iconBackColorOpen : 'transparent' }}
          aria-label="open notifications"
          ref={anchorRef}
          aria-controls={open ? 'notification-grow' : undefined}
          aria-haspopup="true"
          onClick={handleToggle}
        >
          <Badge badgeContent={unreadCount} color="primary">
            <BellOutlined />
          </Badge>
        </IconButton>
      </Tooltip>
      <Popper
        placement="bottom-end"
        open={open}
        anchorEl={anchorRef.current}
        role={undefined}
        transition
        disablePortal
        popperOptions={{
          modifiers: [
            {
              name: 'offset',
              options: {
                offset: [0, 9]
              }
            }
          ]
        }}
      >
        {({ TransitionProps }) => (
          <Transitions type="fade" in={open} {...TransitionProps}>
            <Paper
              sx={{
                boxShadow: theme.customShadows.z1,
                width: 320,
                minWidth: 285,
                maxWidth: { xs: 285, md: 320 }
              }}
            >
              <ClickAwayListener onClickAway={handleClose}>
                <MainCard title="Notifications" elevation={0} border={false} content={false}>
                  {notifications.length === 0 ? (
                    <Box sx={{ p: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        No notifications
                      </Typography>
                    </Box>
                  ) : (
                    <List sx={{ p: 0, maxHeight: 400, overflowY: 'auto' }}>
                      {notifications.map((item) => (
                        <ListItemButton
                          key={item.id}
                          onClick={() => handleRead(item.id)}
                          sx={{ bgcolor: item.read_at ? 'transparent' : 'primary.lighter' }}
                        >
                          <ListItemText
                            primary={
                              <Stack direction="row" spacing={1} alignItems="center">
                                {!item.read_at && (
                                  <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'primary.main' }} />
                                )}
                                <Typography variant="subtitle2">{item.title}</Typography>
                              </Stack>
                            }
                            secondary={item.body || null}
                          />
                        </ListItemButton>
                      ))}
                    </List>
                  )}
                </MainCard>
              </ClickAwayListener>
            </Paper>
          </Transitions>
        )}
      </Popper>
    </Box>
  );
}

Notification.propTypes = {};
