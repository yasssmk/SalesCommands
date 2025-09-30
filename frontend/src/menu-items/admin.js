// assets - Icons pour les éléments admin
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import SettingOutlined from '@ant-design/icons/SettingOutlined';
import IdcardOutlined from '@ant-design/icons/IdcardOutlined';
import SafetyOutlined from '@ant-design/icons/SafetyOutlined'

import { isFeatureEnabled } from '../config/features';

// icons
const icons = { 
  UserOutlined, 
  TeamOutlined, 
  SettingOutlined, 
  IdcardOutlined,
  SafetyOutlined
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
  ENABLE_ROLES: false, // Roles & permissions not ready
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
  id: 'administration',
  title: 'Administration',
  type: 'group',
  icon: icons.SettingOutlined,
  children: [
    {
      id: 'user-management',
      title: 'User Management',
      type: 'item',
      url: '/admin/users',
      icon: icons.UserOutlined,
      breadcrumbs: true,
      wip: false,
    },
    {
      id: 'team-management', 
      title: 'Team Management',
      type: 'item',
      // Don't use the URL if disabled - it prevents accidental navigation
      url: isFeatureEnabled('TEAM_MANAGEMENT') 
        ? '/admin/teams' 
        : '#',
      icon: icons.TeamOutlined,
      breadcrumbs: false,
      disabled: !isFeatureEnabled('TEAM_MANAGEMENT'),
      tooltip: !isFeatureEnabled('TEAM_MANAGEMENT') ? 'Soon' : null,
    },
    {
      id: 'roles-permissions',
      title: 'Roles & Permissions',
      type: 'item',
      url: isFeatureEnabled('ROLES_PERMISSIONS') 
        ? '/admin/roles' 
        : '#',
      icon: icons.SafetyOutlined,
      breadcrumbs: false,
      disabled: !isFeatureEnabled('ROLES_PERMISSIONS'),
      tooltip: !isFeatureEnabled('ROLES_PERMISSIONS') ? 'Soon' : null,
    }
  ] // Show all items
};

export default admin;

// Export feature flags for use in other components
export { FEATURE_FLAGS };