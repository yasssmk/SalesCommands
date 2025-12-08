// frontend/src/menu-items/goToMarket.js

// assets
import RocketOutlined from '@ant-design/icons/RocketOutlined';
import ThunderboltOutlined from '@ant-design/icons/ThunderboltOutlined';
import GlobalOutlined from '@ant-design/icons/GlobalOutlined';
import NotificationOutlined from '@ant-design/icons/NotificationOutlined';
import FundProjectionScreenOutlined from '@ant-design/icons/FundProjectionScreenOutlined';

import { isFeatureEnabled } from '../config/features';

// icons
const icons = {
  RocketOutlined,
  ThunderboltOutlined,
  GlobalOutlined,
  NotificationOutlined,
  FundProjectionScreenOutlined
};

// ==============================|| MENU ITEMS - GO TO MARKET ||============================== //

const goToMarket = {
  id: 'go-to-market-group',
  title: '',
  type: 'group',
  children: [
    {
      id: 'go-to-market-collapse',
      title: 'go-to-market',
      type: 'collapse',
      icon: icons.RocketOutlined,
      breadcrumbs: true,
      children: [
        {
          id: 'action-center',
          title: 'action-center',
          type: 'item',
          url: isFeatureEnabled('ACTION_CENTER') ? '/action-center' : '#',
          icon: icons.ThunderboltOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('ACTION_CENTER'),
          tooltip: !isFeatureEnabled('ACTION_CENTER') ? 'Soon' : null,
        },
        {
          id: 'territories',
          title: 'territories',
          type: 'item',
          url: isFeatureEnabled('TERRITORIES') ? '/territories' : '#',
          icon: icons.GlobalOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('TERRITORIES'),
          tooltip: !isFeatureEnabled('TERRITORIES') ? 'Soon' : null,
        },
        {
          id: 'campaigns',
          title: 'campaigns',
          type: 'item',
          url: isFeatureEnabled('CAMPAIGNS') ? '/campaigns' : '#',
          icon: icons.NotificationOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('CAMPAIGNS'),
          tooltip: !isFeatureEnabled('CAMPAIGNS') ? 'Soon' : null,
        },
        {
          id: 'sales-plan',
          title: 'sales-plan',
          type: 'item',
          url: isFeatureEnabled('SALES_PLAN') ? '/sales-plan' : '#',
          icon: icons.FundProjectionScreenOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('SALES_PLAN'),
          tooltip: !isFeatureEnabled('SALES_PLAN') ? 'Soon' : null,
        }
      ]
    }
  ]
};

export default goToMarket;