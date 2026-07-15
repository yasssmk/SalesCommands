import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import { formatDateTime } from 'config/formatters';
import { ResponseStatus } from 'api/notifications/notifications';

// assets
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// ==============================|| NOTIFICATION ROW ||============================== //

/**
 * One notification row. Clicking the row marks it read and deep-links (onClick).
 * Actionable invitations (response_status === PENDING) also show Accept /
 * Decline buttons; those call stopPropagation FIRST so responding never triggers
 * the row's mark-read + navigation.
 */
export default function NotificationRow({ item, onClick, onRespond }) {
  const isPending = item.response_status === ResponseStatus.PENDING;

  const handleRespondClick = (event, responseStatus) => {
    // Critical: the row is the click target (mark-read + navigate). Stop the
    // event here so Accept / Decline act only on the invitation.
    event.stopPropagation();
    onRespond(responseStatus);
  };

  return (
    <ListItemButton onClick={onClick} sx={{ bgcolor: item.read_at ? 'transparent' : 'primary.lighter' }}>
      <ListItemText
        primary={
          <Stack direction="row" spacing={1} alignItems="center">
            {!item.read_at && <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'primary.main' }} />}
            <Typography variant="subtitle2">{item.title}</Typography>
          </Stack>
        }
        secondary={
          <Stack component="span" spacing={0.25}>
            {item.body ? (
              <Typography variant="body2" color="text.secondary" component="span">
                {item.body}
              </Typography>
            ) : null}
            <Typography variant="caption" color="text.secondary" component="span">
              {formatDateTime(item.created_at)}
            </Typography>
            {isPending ? (
              <Stack component="span" direction="row" spacing={1} sx={{ pt: 0.75 }}>
                <Button
                  size="small"
                  variant="contained"
                  color="success"
                  startIcon={<CheckOutlined />}
                  onClick={(event) => handleRespondClick(event, ResponseStatus.ACCEPTED)}
                >
                  Accept
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="inherit"
                  startIcon={<CloseOutlined />}
                  onClick={(event) => handleRespondClick(event, ResponseStatus.DECLINED)}
                >
                  Decline
                </Button>
              </Stack>
            ) : null}
          </Stack>
        }
        secondaryTypographyProps={{ component: 'div' }}
      />
    </ListItemButton>
  );
}

NotificationRow.propTypes = {
  item: PropTypes.object,
  onClick: PropTypes.func,
  onRespond: PropTypes.func,
};
