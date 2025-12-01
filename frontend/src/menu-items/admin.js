// assets - Icons pour les éléments admin
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import SettingOutlined from '@ant-design/icons/SettingOutlined';
import IdcardOutlined from '@ant-design/icons/IdcardOutlined';
import SafetyOutlined from '@ant-design/icons/SafetyOutlined';
import BankOutlined from '@ant-design/icons/BankOutlined';

import { isFeatureEnabled } from '../config/features';

// icons
const icons = { 
  UserOutlined, 
  TeamOutlined, 
  SettingOutlined, 
  IdcardOutlined,
  SafetyOutlined,
  BankOutlined
};

// ==============================|| FEATURE FLAGS ||============================== //

/**
 * Feature flags for Work In Progress items
 * In production: set all to false to hide WIP items
 * In development: set to true to show disabled/coming-soon items
 */
const FEATURE_FLAGS = {
  SHOW_WIP_ITEMS: process.env.NODE_ENV === 'development', // Auto-hide in production
  ENABLE_TEAMS: false, // Team management not ready
  ENABLE_ORGANIZATIONS: false, // Organizations not ready
  ENABLE_ROLES: false, // Roles & permissions not ready,
  ACCOUNT_MANAGEMENT: true,
};


// ==============================|| MENU ITEMS - ADMINISTRATION ||============================== //

/**
 * Section Administration - MVP
 * 
 * Structure identique au modèle (crm.jsx, widget.jsx) :
 * - id unique pour la section
 * - title affiché dans le drawer
 * - type: 'group' pour créer une section avec divider
 * - children: array d'éléments menu
 * 
 * Tous les messages en anglais comme demandé dans les règles
 */
const admin = {
  id: 'administration-group',
  title: 'administration',
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
          url: isFeatureEnabled('TEAM_MANAGEMENT') 
            ? '/admin/teams' 
            : '#',
          icon: icons.TeamOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('TEAM_MANAGEMENT'),
          tooltip: !isFeatureEnabled('TEAM_MANAGEMENT') ? 'Soon' : null,
        },
        {
          id: 'roles-permissions',
          title: 'roles-permissions',
          type: 'item',
          url: isFeatureEnabled('ROLES_PERMISSIONS') 
            ? '/admin/roles' 
            : '#',
          icon: icons.SafetyOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('ROLES_PERMISSIONS'),
          tooltip: !isFeatureEnabled('ROLES_PERMISSIONS') ? 'Soon' : null,
        },
        {
          id: 'account-management',
          title: 'account-management',
          type: 'item',
          url: isFeatureEnabled('ACCOUNT_MANAGEMENT') 
            ? '/admin/accounts' 
            : '#',
          icon: icons.BankOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('ACCOUNT_MANAGEMENT'),
          tooltip: !isFeatureEnabled('ACCOUNT_MANAGEMENT') ? 'Soon' : null,
        }
      ]
    }
  ]
};

export default admin;

// Export feature flags for use in other components
export { FEATURE_FLAGS };