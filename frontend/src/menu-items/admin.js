// frontend/src/menu-items/admin.js

// assets
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import SettingOutlined from '@ant-design/icons/SettingOutlined';
import SafetyOutlined from '@ant-design/icons/SafetyOutlined';

import { isFeatureEnabled } from '../config/features';

// icons
const icons = { 
  UserOutlined, 
  TeamOutlined, 
  SettingOutlined, 
  SafetyOutlined
};

// ==============================|| MENU ITEMS - ADMINISTRATION ||============================== //

const admin = {
  id: 'administration-group',
  title: '',
  type: 'group',
  children: [
    {
      id: 'administration-collapse',        
      title: 'administration',               
      type: 'collapse',                      
      icon: icons.SettingOutlined,          
      breadcrumbs: true,                     
      children: [
        {
          id: 'user-management',
          title: 'user-management',
          type: 'item',
          url: '/admin/users',
          icon: icons.UserOutlined,
          breadcrumbs: true,
        },
        {
          id: 'team-management', 
          title: 'team-management',
          type: 'item',
          url: isFeatureEnabled('TEAM_MANAGEMENT') ? '/admin/teams' : '#',
          icon: icons.TeamOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('TEAM_MANAGEMENT'),
          tooltip: !isFeatureEnabled('TEAM_MANAGEMENT') ? 'Soon' : null,
        },
        {
          id: 'roles-permissions',
          title: 'roles-permissions',
          type: 'item',
          url: isFeatureEnabled('ROLES_PERMISSIONS') ? '/admin/roles' : '#',
          icon: icons.SafetyOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('ROLES_PERMISSIONS'),
          tooltip: !isFeatureEnabled('ROLES_PERMISSIONS') ? 'Soon' : null,
        }
      ]
    }
  ]
};

export default admin;