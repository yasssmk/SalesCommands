import PropTypes from 'prop-types';
import useMediaQuery from '@mui/material/useMediaQuery';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Link from '@mui/material/Link';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemSecondaryAction from '@mui/material/ListItemSecondaryAction';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import DialogContent from '@mui/material/DialogContent';
import Button from '@mui/material/Button';

// third-party
import { PatternFormat } from 'react-number-format';
import ToolOutlined from '@ant-design/icons/ToolOutlined';

// project import
import MainCard from 'components/MainCard';
import Avatar from 'components/@extended/Avatar';

// assets
import EnvironmentOutlined from '@ant-design/icons/EnvironmentOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import BankOutlined from '@ant-design/icons/BankOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';

// ==============================|| EXPANDING TABLE - USER DETAILS ||============================== //

export default function ExpandingUserDetail({ data }) {
  const downMD = useMediaQuery((theme) => theme.breakpoints.down('md'));

  const handlePlaceholderAction = () => {
      openSnackbar({
        open: true,
        message: 'User detail is under construction. Coming soon!',
        variant: 'alert',
        alert: {
          color: 'info'
        }
      });
    };

  return (
    <Grid container spacing={2.5} sx={{ pl: { xs: 0, sm: 5, md: 6, lg: 10, xl: 12 } }}>
      <DialogContent sx={{ p: 4 }}>
        <Stack spacing={3} alignItems="center" justifyContent="center" sx={{ minHeight: 300 }}>
          <ToolOutlined style={{ fontSize: '4rem', color: '#1976d2' }} />
          <Typography variant="h4" color="primary">
            In construction...
          </Typography>
          <Typography variant="body1" color="text.secondary" textAlign="center">
            User detail is under construction. 
            <br />
            Coming soon!
          </Typography>
          <Button 
            variant="outlined" 
            color="primary" 
            onClick={handlePlaceholderAction}
            sx={{ mt: 2 }}
          >
            Know more.
          </Button>
        </Stack>
      </DialogContent>
    </Grid>
  );
}

ExpandingUserDetail.propTypes = { data: PropTypes.any };
