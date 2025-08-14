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

// third-party
import { PatternFormat } from 'react-number-format';

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

  return (
    <Grid container spacing={2.5} sx={{ pl: { xs: 0, sm: 5, md: 6, lg: 10, xl: 12 } }}>
      <Grid item xs={12} sm={5} md={4} xl={3.5}>
        <MainCard>
          <Chip
            label={data.is_active ? 'Active' : 'Inactive'}
            size="small"
            color={data.is_active ? 'success' : 'error'}
            variant="light"
            sx={{
              position: 'absolute',
              right: 10,
              top: 10,
              zIndex: 1
            }}
          />
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Stack spacing={2.5} alignItems="center">
                <Avatar 
                  alt="User Avatar" 
                  size="xl" 
                  src={`/assets/images/users/avatar-${!data.avatar ? 1 : data.avatar}.png`}
                >
                  {data.first_name?.charAt(0)}{data.last_name?.charAt(0)}
                </Avatar>
                <Stack spacing={0.5} alignItems="center">
                  <Typography variant="h5">
                    {`${data.first_name || ''} ${data.last_name || ''}`.trim() || 'No Name'}
                  </Typography>
                  <Typography color="secondary">{data.role_name || 'No Role'}</Typography>
                </Stack>
              </Stack>
            </Grid>
            <Grid item xs={12}>
              <Divider />
            </Grid>
            <Grid item xs={12}>
              <List component="nav" aria-label="main mailbox folders" sx={{ py: 0, '& .MuiListItem-root': { p: 0, py: 1 } }}>
                <ListItem>
                  <ListItemIcon>
                    <MailOutlined />
                  </ListItemIcon>
                  <ListItemText primary={<Typography color="secondary">Email</Typography>} />
                  <ListItemSecondaryAction>
                    <Typography align="right">{data.email}</Typography>
                  </ListItemSecondaryAction>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <UserOutlined />
                  </ListItemIcon>
                  <ListItemText primary={<Typography color="secondary">User ID</Typography>} />
                  <ListItemSecondaryAction>
                    <Typography align="right">#{data.id}</Typography>
                  </ListItemSecondaryAction>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <BankOutlined />
                  </ListItemIcon>
                  <ListItemText primary={<Typography color="secondary">Organization</Typography>} />
                  <ListItemSecondaryAction>
                    <Typography align="right">{data.organization?.name || 'No Organization'}</Typography>
                  </ListItemSecondaryAction>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <TeamOutlined />
                  </ListItemIcon>
                  <ListItemText primary={<Typography color="secondary">Team</Typography>} />
                  <ListItemSecondaryAction>
                    <Typography align="right">{data.team?.name || 'No Team'}</Typography>
                  </ListItemSecondaryAction>
                </ListItem>
              </List>
            </Grid>
          </Grid>
        </MainCard>
      </Grid>
      <Grid item xs={12} sm={7} md={8} xl={8.5}>
        <Stack spacing={2.5}>
          <MainCard title="User Details">
            <List sx={{ py: 0 }}>
              <ListItem divider={!downMD}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">First Name</Typography>
                      <Typography>{data.first_name || 'Not specified'}</Typography>
                    </Stack>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Last Name</Typography>
                      <Typography>{data.last_name || 'Not specified'}</Typography>
                    </Stack>
                  </Grid>
                </Grid>
              </ListItem>
              <ListItem divider={!downMD}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Email Address</Typography>
                      <Typography>{data.email}</Typography>
                    </Stack>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Role</Typography>
                      <Chip 
                        label={data.role_name || 'No Role'} 
                        size="small" 
                        variant="light"
                        color={
                          data.role_name === 'Admin' ? 'error' :
                          data.role_name === 'Manager' ? 'warning' :
                          data.role_name === 'User' ? 'primary' : 'default'
                        }
                      />
                    </Stack>
                  </Grid>
                </Grid>
              </ListItem>
              <ListItem divider={!downMD}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Account Status</Typography>
                      <Chip
                        color={data.is_active ? 'success' : 'error'}
                        label={data.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        variant="light"
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Staff Access</Typography>
                      <Chip
                        color={data.is_staff ? 'warning' : 'default'}
                        label={data.is_staff ? 'Staff Member' : 'Regular User'}
                        size="small"
                        variant="light"
                      />
                    </Stack>
                  </Grid>
                </Grid>
              </ListItem>
              <ListItem>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Organization</Typography>
                      <Typography>{data.organization?.name || 'No Organization Assigned'}</Typography>
                    </Stack>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Team</Typography>
                      <Typography>{data.team?.name || 'No Team Assigned'}</Typography>
                    </Stack>
                  </Grid>
                </Grid>
              </ListItem>
            </List>
          </MainCard>
          <MainCard title="Account Information">
            <List sx={{ py: 0 }}>
              <ListItem divider>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Client Account</Typography>
                      <Typography>{data.client_account?.name || 'No Client'}</Typography>
                    </Stack>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">User ID</Typography>
                      <Typography>#{data.id}</Typography>
                    </Stack>
                  </Grid>
                </Grid>
              </ListItem>
              <ListItem>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Created Date</Typography>
                      <Typography>
                        {data.created_at ? new Date(data.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric'
                        }) : 'Not specified'}
                      </Typography>
                    </Stack>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Stack spacing={0.5}>
                      <Typography color="secondary">Last Updated</Typography>
                      <Typography>
                        {data.updated_at ? new Date(data.updated_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric'
                        }) : 'Not specified'}
                      </Typography>
                    </Stack>
                  </Grid>
                </Grid>
              </ListItem>
            </List>
          </MainCard>
        </Stack>
      </Grid>
    </Grid>
  );
}

ExpandingUserDetail.propTypes = { data: PropTypes.any };