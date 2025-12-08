// frontend/src/menu-items/businessData.js

// assets
import DatabaseOutlined from '@ant-design/icons/DatabaseOutlined';
import BankOutlined from '@ant-design/icons/BankOutlined';
import ContactsOutlined from '@ant-design/icons/ContactsOutlined';
import ShoppingOutlined from '@ant-design/icons/ShoppingOutlined';

import { isFeatureEnabled } from '../config/features';

// icons
const icons = {
  DatabaseOutlined,
  BankOutlined,
  ContactsOutlined,
  ShoppingOutlined
};

// ==============================|| MENU ITEMS - BUSINESS DATA ||============================== //

const businessData = {
  id: 'business-data-group',
  title: '',
  type: 'group',
  children: [
    {
      id: 'business-data-collapse',
      title: 'business-data',
      type: 'collapse',
      icon: icons.DatabaseOutlined,
      breadcrumbs: true,
      children: [
        {
          id: 'account-management',
          title: 'account-management',
          type: 'item',
          url: isFeatureEnabled('ACCOUNT_MANAGEMENT') ? '/admin/accounts' : '#',
          icon: icons.BankOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('ACCOUNT_MANAGEMENT'),
          tooltip: !isFeatureEnabled('ACCOUNT_MANAGEMENT') ? 'Soon' : null,
        },
        {
          id: 'contacts-management',
          title: 'contacts-management',
          type: 'item',
          url: isFeatureEnabled('CONTACTS_MANAGEMENT') ? '/admin/contacts' : '#',
          icon: icons.ContactsOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('CONTACTS_MANAGEMENT'),
          tooltip: !isFeatureEnabled('CONTACTS_MANAGEMENT') ? 'Soon' : null,
        },
        {
          id: 'products-management',
          title: 'products-management',
          type: 'item',
          url: isFeatureEnabled('PRODUCTS_MANAGEMENT') ? '/admin/products' : '#',
          icon: icons.ShoppingOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled('PRODUCTS_MANAGEMENT'),
          tooltip: !isFeatureEnabled('PRODUCTS_MANAGEMENT') ? 'Soon' : null,
        }
      ]
    }
  ]
};

export default businessData;