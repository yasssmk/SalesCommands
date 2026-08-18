// frontend/src/menu-items/businessData.js

// assets
import DatabaseOutlined from "@ant-design/icons/DatabaseOutlined";
import BankOutlined from "@ant-design/icons/BankOutlined";
import ShoppingOutlined from "@ant-design/icons/ShoppingOutlined";
import DeploymentUnitOutlined from "@ant-design/icons/DeploymentUnitOutlined";

import { isFeatureEnabled } from "../config/features";

// icons
const icons = {
  DatabaseOutlined,
  BankOutlined,
  ShoppingOutlined,
  DeploymentUnitOutlined,
};

// ==============================|| MENU ITEMS - BUSINESS DATA ||============================== //

const businessData = {
  id: "business-data-group",
  title: "",
  type: "group",
  children: [
    {
      id: "business-data-collapse",
      title: "business-data",
      type: "collapse",
      icon: icons.DatabaseOutlined,
      breadcrumbs: true,
      children: [
        {
          id: "account-management",
          title: "account-management",
          type: "item",
          url: isFeatureEnabled("ACCOUNT_MANAGEMENT")
            ? "/businessData/accounts"
            : "#",
          icon: icons.BankOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled("ACCOUNT_MANAGEMENT"),
          tooltip: !isFeatureEnabled("ACCOUNT_MANAGEMENT") ? "Soon" : null,
        },
        {
          id: "decision-cycles",
          title: "decision-cycles",
          type: "item",
          url: isFeatureEnabled("DECISION_CYCLES")
            ? "/businessData/decisionCycles"
            : "#",
          icon: icons.DeploymentUnitOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled("DECISION_CYCLES"),
          tooltip: !isFeatureEnabled("DECISION_CYCLES") ? "Soon" : null,
        },
        {
          id: "products-management",
          title: "products-management",
          type: "item",
          url: isFeatureEnabled("PRODUCTS_MANAGEMENT")
            ? "/businessData/products"
            : "#",
          icon: icons.ShoppingOutlined,
          breadcrumbs: true,
          disabled: !isFeatureEnabled("PRODUCTS_MANAGEMENT"),
          tooltip: !isFeatureEnabled("PRODUCTS_MANAGEMENT") ? "Soon" : null,
        },
      ],
    },
  ],
};

export default businessData;
