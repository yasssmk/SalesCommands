import PropTypes from 'prop-types';

// next
import { useRouter } from 'next/navigation';

// material-ui
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';

// assets
import AimOutlined from '@ant-design/icons/AimOutlined';
import LogoutOutlined from '@ant-design/icons/LogoutOutlined';

// ==============================|| HEADER PROFILE - PROFILE TAB ||============================== //

const OBJECTIVES_ROUTE = '/objectives';

export default function ProfileTab({ handleLogout }) {
  const router = useRouter();

  return (
    <List component="nav" sx={{ p: 0, '& .MuiListItemIcon-root': { minWidth: 32 } }}>
      <ListItemButton onClick={() => router.push(OBJECTIVES_ROUTE)}>
        <ListItemIcon>
          <AimOutlined />
        </ListItemIcon>
        <ListItemText primary="My Objectives" />
      </ListItemButton>
      <ListItemButton onClick={handleLogout}>
        <ListItemIcon>
          <LogoutOutlined />
        </ListItemIcon>
        <ListItemText primary="Logout" />
      </ListItemButton>
    </List>
  );
}

ProfileTab.propTypes = { handleLogout: PropTypes.func };
