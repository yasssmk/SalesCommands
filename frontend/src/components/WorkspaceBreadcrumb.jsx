// frontend/src/components/WorkspaceBreadcrumb.jsx
/**
 * Workspace Breadcrumb Component
 * 
 * Provides consistent navigation breadcrumbs across workspace pages.
 * Supports multiple context paths:
 * - Account > Decision Cycle > Step
 * - Account > Activity
 * - Territory > Account > Activity
 * - Account > Decision Cycle > Step > Activity
 * 
 * Used in:
 * - Step detail page header
 * - Activity workspace header
 */

'use client';

import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// material-ui
import Breadcrumbs from '@mui/material/Breadcrumbs';
import Link from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

// ant-design icons
import HomeOutlined from '@ant-design/icons/HomeOutlined';
import RightOutlined from '@ant-design/icons/RightOutlined';

// ==============================|| BREADCRUMB ITEM ||============================== //

/**
 * Single breadcrumb item - clickable link or plain text
 */
function BreadcrumbItem({ label, href, isLast, icon: Icon }) {
  const theme = useTheme();
  const router = useRouter();

  const handleClick = (e) => {
    e.preventDefault();
    if (href) {
      router.push(href);
    }
  };

  // Last item is not clickable
  if (isLast) {
    return (
      <Typography
        variant="body2"
        color="text.primary"
        fontWeight={500}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          maxWidth: 200,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap'
        }}
      >
        {Icon && <Icon style={{ fontSize: 14 }} />}
        {label}
      </Typography>
    );
  }

  return (
    <Link
      href={href}
      onClick={handleClick}
      underline="hover"
      color="text.secondary"
      variant="body2"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.5,
        cursor: 'pointer',
        maxWidth: 180,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        '&:hover': {
          color: theme.palette.primary.main
        }
      }}
    >
      {Icon && <Icon style={{ fontSize: 14 }} />}
      {label}
    </Link>
  );
}

BreadcrumbItem.propTypes = {
  label: PropTypes.string.isRequired,
  href: PropTypes.string,
  isLast: PropTypes.bool,
  icon: PropTypes.elementType
};

// ==============================|| WORKSPACE BREADCRUMB ||============================== //

/**
 * WorkspaceBreadcrumb Component
 * 
 * @param {Object[]} items - Array of breadcrumb items
 * @param {string} items[].label - Display text
 * @param {string} items[].href - Navigation URL (optional for last item)
 * @param {React.ElementType} items[].icon - Optional icon component
 * @param {boolean} showHome - Whether to show home icon as first item
 * @param {string} homeHref - URL for home link
 */
export default function WorkspaceBreadcrumb({
  items = [],
  showHome = false,
  homeHref = '/territories'
}) {
  const allItems = showHome
    ? [{ label: 'Home', href: homeHref, icon: HomeOutlined }, ...items]
    : items;

  if (allItems.length === 0) {
    return null;
  }

  return (
    <Breadcrumbs
      separator={<RightOutlined style={{ fontSize: 10, color: '#999' }} />}
      aria-label="workspace navigation"
      sx={{ mb: 1 }}
    >
      {allItems.map((item, index) => (
        <BreadcrumbItem
          key={index}
          label={item.label}
          href={item.href}
          icon={item.icon}
          isLast={index === allItems.length - 1}
        />
      ))}
    </Breadcrumbs>
  );
}

// ==============================|| PROP TYPES ||============================== //

WorkspaceBreadcrumb.propTypes = {
  items: PropTypes.arrayOf(
    PropTypes.shape({
      label: PropTypes.string.isRequired,
      href: PropTypes.string,
      icon: PropTypes.elementType
    })
  ),
  showHome: PropTypes.bool,
  homeHref: PropTypes.string
};

// ==============================|| HELPER BUILDERS ||============================== //

/**
 * Build breadcrumb items for Activity workspace
 * 
 * @param {Object} params
 * @param {string} params.accountId - Account UUID
 * @param {string} params.accountName - Account display name
 * @param {string} params.stepId - Optional Step UUID (if activity linked to step)
 * @param {string} params.stepName - Optional Step name
 * @param {string} params.activityTitle - Activity title (current page)
 * @param {string} params.fromContext - 'account' | 'territory' | 'step'
 * @param {string} params.territoryId - Optional Territory UUID
 * @param {string} params.territoryName - Optional Territory name
 * @returns {Object[]} Breadcrumb items array
 */
export function buildActivityBreadcrumbs({
  accountId,
  accountName,
  cycleId,
  stepId,
  stepName,
  activityTitle,
  fromContext = 'account',
  territoryId,
  territoryName
}) {
  const items = [];
  const cycleParam = cycleId ? `&cycle=${cycleId}` : '';

  // Add territory if coming from territory context
  if (fromContext === 'territory' && territoryId) {
    items.push({
      label: territoryName || 'Territory',
      href: `/territories/${territoryId}?tab=activities`
    });
  }

  // Always add account — link to decision-cycle tab with cycle context
  items.push({
    label: accountName || 'Account',
    href: `/accounts/${accountId}?tab=decision-cycle${cycleParam}`
  });

  // Add step if activity is linked to a step.
  // Routes to the DC workspace TIMELINE tab of the step's parent cycle
  // (the per-step workspace is being retired). Falls back to the account's
  // decision-cycle tab when the cycle id is unavailable, so the crumb never
  // builds a broken `/dc/undefined` link.
  if (stepId && stepName) {
    items.push({
      label: stepName,
      href: cycleId
        ? `/accounts/${accountId}/dc/${cycleId}?tab=timeline`
        : `/accounts/${accountId}?tab=decision-cycle`
    });
  }

  // Current page (activity)
  items.push({
    label: activityTitle || 'Activity'
    // No href - current page
  });

  return items;
}

/**
 * Build breadcrumb items for Decision Cycle workspace
 *
 * @param {Object} params
 * @param {string} params.accountId - Account UUID
 * @param {string} params.accountName - Account display name
 * @param {string} params.cycleName - Decision Cycle name (current page)
 * @returns {Object[]} Breadcrumb items array
 */
export function buildDCWorkspaceBreadcrumbs({ accountId, accountName, cycleName }) {
  return [
    {
      label: accountName || 'Account',
      href: `/accounts/${accountId}?tab=decision-cycle`
    },
    {
      label: cycleName || 'Decision Cycle'
      // No href - current page
    }
  ];
}

/**
 * Build breadcrumb items for Territory workspace
 * 
 * @param {Object} params
 * @param {string} params.territoryName - Territory name (current page)
 * @returns {Object[]} Breadcrumb items array
 */
export function buildTerritoryBreadcrumbs({ territoryName }) {
  return [
    {
      label: 'Territories',
      href: '/territories'
    },
    {
      label: territoryName || 'Territory'
      // No href - current page
    }
  ];
}
