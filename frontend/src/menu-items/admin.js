// assets - Icons pour les éléments admin
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import SettingOutlined from '@ant-design/icons/SettingOutlined';
import IdcardOutlined from '@ant-design/icons/IdcardOutlined';

// icons
const icons = { 
  UserOutlined, 
  TeamOutlined, 
  SettingOutlined, 
  IdcardOutlined 
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
  title: 'Administration tah le hood',
  type: 'group',
  icon: icons.SettingOutlined,
  children: [
    {
      id: 'user-management',
      title: 'User Management',
      type: 'item',
      url: '/admin/users',
      icon: icons.UserOutlined,
      breadcrumbs: true
    },
    {
      id: 'team-management', 
      title: 'Ekip Management',
      type: 'item',
      url: '/admin/teams',
      icon: icons.TeamOutlined,
      breadcrumbs: false
    },
    {
      id: 'organization-management',
      title: 'Organizations',
      type: 'item', 
      url: '/admin/organizations',
      icon: icons.IdcardOutlined,
      breadcrumbs: false
    },
    {
      id: 'roles-permissions',
      title: 'Roles & Permissions',
      type: 'item',
      url: '/admin/roles',
      icon: icons.SettingOutlined,
      breadcrumbs: false
    }
  ]
};

export default admin;