// third-party
import { FormattedMessage } from 'react-intl';

// assets
import LineChartOutlined from '@ant-design/icons/LineChartOutlined';
import IdcardOutlined from '@ant-design/icons/IdcardOutlined';
import DatabaseOutlined from '@ant-design/icons/DatabaseOutlined';

// type

// icons
const icons = { LineChartOutlined, IdcardOutlined, DatabaseOutlined };

// ==============================|| MENU ITEMS - DASHBOARD ||============================== //

const CRM = {
  id: 'crm',
  title: <FormattedMessage id="crm" />,
  icon: icons.IdcardOutlined,
  type: 'group',
  children: [
    {
      id: 'accounts',
      title: <FormattedMessage id="accounts" />,
      type: 'item',
      url: '/crm/accounts/table',
      icon: icons.DatabaseOutlined
    }
  ]
};

export default CRM;
