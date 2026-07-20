// frontend/src/menu-items/home.js

// assets
import HomeOutlined from '@ant-design/icons/HomeOutlined';

// icons
const icons = {
  HomeOutlined
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
    }
  ]
};

export default home;
