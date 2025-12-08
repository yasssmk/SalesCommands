// frontend/src/menu-items/home.js

// assets
import HomeOutlined from '@ant-design/icons/HomeOutlined';
import DashboardOutlined from '@ant-design/icons/DashboardOutlined';

import { isFeatureEnabled } from '../config/features';

// icons
const icons = {
  HomeOutlined,
  DashboardOutlined
};

// ==============================|| MENU ITEMS - HOME ||============================== //

const home = {
  id: 'home-group',
  title: '',
  type: 'group',
  children: [
    {
      id: 'home',
      title: 'home',
      type: 'item',
      url: '/',
      icon: icons.HomeOutlined,
      breadcrumbs: false,
    },
    {
      id: 'dashboard',
      title: 'dashboard',
      type: 'item',
      url: isFeatureEnabled('DASHBOARD') ? '/dashboard' : '#',
      icon: icons.DashboardOutlined,
      breadcrumbs: true,
      disabled: !isFeatureEnabled('DASHBOARD'),
      tooltip: !isFeatureEnabled('DASHBOARD') ? 'Soon' : null,
    }
  ]
};

export default home;