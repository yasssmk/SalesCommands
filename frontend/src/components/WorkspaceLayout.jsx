// frontend/src/components/WorkspaceLayout.jsx
/**
 * WorkspaceLayout — Shared layout for all workspace pages.
 *
 * Enforces identical spacing, structure, and visual rhythm across:
 * - Activity workspace
 * - Decision Step workspace
 * - Account workspace
 * - Territory workspace
 *
 * Structure:
 *   1. Breadcrumb navigation (mb: 2)
 *   2. Header MainCard (mb: 2)
 *      - Row 1: Avatar + Title (editable or read-only) + Actions slot
 *      - Row 2: Chips
 *      - Divider
 *      - Row 3: Info items (icon + label nodes)
 *   3. Tabs (borderBottom, background.paper)
 *   4. Content MainCard (mt: 0, flush top corners with tabs)
 *
 * Usage:
 *   <WorkspaceLayout
 *     breadcrumbs={breadcrumbItems}
 *     avatar={<Avatar sx={{ width: 56, height: 56, bgcolor: 'info.main' }}><PhoneOutlined /></Avatar>}
 *     title="Call with Acme"
 *     onTitleSave={handleSave}
 *     headerActions={<ActionsMenu />}
 *     chips={[<Chip label="Planned" color="info" size="small" />]}
 *     infoItems={[<InfoNode />, <InfoNode />]}
 *     tabs={[{ id: 'overview', label: 'Overview' }]}
 *     activeTab="overview"
 *     onTabChange={handleTabChange}
 *     loading={isLoading}
 *   >
 *     {renderTabContent()}
 *   </WorkspaceLayout>
 */

'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';

// Project imports
import MainCard from 'components/MainCard';
import WorkspaceBreadcrumb from 'components/WorkspaceBreadcrumb';
import EditableField from 'sections/accounts/workspace/EditableField';

// ==============================|| HEADER SKELETON ||============================== //

/**
 * Standard skeleton shown while workspace data is loading.
 * Matches the 3-row header structure exactly.
 */
function WorkspaceHeaderSkeleton() {
  return (
    <MainCard sx={{ mb: 2 }}>
      <Stack spacing={2}>
        {/* Row 1: Avatar + Title */}
        <Stack direction="row" alignItems="center" spacing={2}>
          <Skeleton variant="circular" width={56} height={56} />
          <Skeleton variant="text" width={260} height={40} />
          <Box flex={1} />
          <Skeleton variant="circular" width={32} height={32} />
        </Stack>

        {/* Row 2: Chips */}
        <Stack direction="row" spacing={1}>
          <Skeleton variant="rectangular" width={80} height={24} sx={{ borderRadius: 4 }} />
          <Skeleton variant="rectangular" width={90} height={24} sx={{ borderRadius: 4 }} />
        </Stack>

        {/* Divider */}
        <Divider />

        {/* Row 3: Info items */}
        <Stack direction="row" spacing={3}>
          <Skeleton variant="text" width={140} height={20} />
          <Skeleton variant="text" width={120} height={20} />
          <Skeleton variant="text" width={100} height={20} />
        </Stack>
      </Stack>
    </MainCard>
  );
}

// ==============================|| TABS SKELETON ||============================== //

function WorkspaceTabsSkeleton() {
  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper', px: 2, py: 1.5 }}>
      <Stack direction="row" spacing={3}>
        <Skeleton variant="text" width={70} height={24} />
        <Skeleton variant="text" width={80} height={24} />
        <Skeleton variant="text" width={60} height={24} />
      </Stack>
    </Box>
  );
}

// ==============================|| WORKSPACE LAYOUT ||============================== //

function WorkspaceLayoutInner({
  // Navigation
  breadcrumbs,

  // Header — Row 1
  avatar,
  title,
  onTitleSave,
  titleDisabled = false,
  headerActions,

  // Header — Row 2 (chips)
  chips,

  // Header — Extra rows (between chips and divider)
  extraRows,

  // Header — Info items (after divider)
  infoItems,

  // Tabs
  tabs,
  activeTab,
  onTabChange,

  // State
  loading = false,

  // Content
  children
}) {

  // ==============================|| TAB CHANGE HANDLER ||============================== //

  const handleTabChange = (event, newValue) => {
    onTabChange(newValue);
  };

  // ==============================|| LOADING STATE ||============================== //

  if (loading) {
    return (
      <Box>
        {/* Breadcrumb placeholder */}
        {breadcrumbs && (
          <Box sx={{ mb: 2 }}>
            <Skeleton variant="text" width={300} height={20} />
          </Box>
        )}

        {/* Header skeleton */}
        <WorkspaceHeaderSkeleton />

        {/* Tabs skeleton */}
        <WorkspaceTabsSkeleton />

        {/* Content skeleton */}
        <MainCard sx={{ mt: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
          <Stack spacing={2} sx={{ py: 4 }}>
            <Skeleton variant="text" width="60%" height={24} />
            <Skeleton variant="text" width="80%" height={24} />
            <Skeleton variant="rectangular" width="100%" height={120} sx={{ borderRadius: 1 }} />
          </Stack>
        </MainCard>
      </Box>
    );
  }

  // ==============================|| RENDER ||============================== //

  // Filter out null/undefined info items and chips
  const validChips = (chips || []).filter(Boolean);
  const validExtraRows = (extraRows || []).filter(Boolean);
  const validInfoItems = (infoItems || []).filter(Boolean);

  return (
    // The workspace drawer coque was lifted to DashboardLayout (UX Activity L2)
    // so it covers every view; WorkspaceLayout now renders only the workspace's
    // own header / tabs / content column.
    <Box>
      {/* ==================== BREADCRUMB ==================== */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <WorkspaceBreadcrumb items={breadcrumbs} />
        </Box>
      )}

      {/* ==================== HEADER CARD ==================== */}
      <MainCard sx={{ mb: 2 }}>
        <Stack spacing={2}>
          {/* Row 1: Avatar + Title + Actions */}
          <Stack direction="row" alignItems="center" spacing={2} sx={{ flexWrap: 'wrap' }}>
            {avatar}

            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              {onTitleSave ? (
                <EditableField
                  value={title}
                  fieldKey="title"
                  onSave={onTitleSave}
                  placeholder="Untitled..."
                  variant="h3"
                  typographyProps={{ component: 'h1', noWrap: true }}
                  disabled={titleDisabled}
                />
              ) : (
                <Typography variant="h3" component="h1" noWrap>
                  {title}
                </Typography>
              )}
            </Box>

            {headerActions}
          </Stack>

          {/* Row 2: Chips */}
          {validChips.length > 0 && (
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              {validChips}
            </Stack>
          )}

          {/* Extra rows (optional, between chips and divider) */}
          {validExtraRows.map((row, index) => (
            <Box key={index}>{row}</Box>
          ))}

          {/* Divider */}
          <Divider />

          {/* Info items (row after divider) */}
          {validInfoItems.length > 0 && (
            <Stack direction="row" spacing={3} alignItems="center" flexWrap="wrap" useFlexGap>
              {validInfoItems}
            </Stack>
          )}

        </Stack>
      </MainCard>

      {/* ==================== TABS ==================== */}
      {tabs && tabs.length > 0 && (
        <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            variant="scrollable"
            scrollButtons="auto"
            allowScrollButtonsMobile
            aria-label="workspace tabs"
          >
            {tabs.map((tab) => (
              <Tab
                key={tab.id}
                value={tab.id}
                label={tab.label}
                id={`workspace-tab-${tab.id}`}
                aria-controls={`workspace-tabpanel-${tab.id}`}
                disabled={tab.disabled}
                sx={tab.disabled ? { opacity: 0.5 } : undefined}
              />
            ))}
          </Tabs>
        </Box>
      )}

      {/* ==================== TAB CONTENT ==================== */}
      <MainCard sx={{ mt: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
        {children}
      </MainCard>
    </Box>
  );
}

// ==============================|| EXPORT ||============================== //

// The WorkspaceDrawerProvider + coque were lifted to DashboardLayout (L2); this
// component is now just the workspace's header / tabs / content.
export default function WorkspaceLayout(props) {
  return <WorkspaceLayoutInner {...props} />;
}

// ==============================|| PROP TYPES ||============================== //

WorkspaceLayoutInner.propTypes = {
  /** Breadcrumb items for WorkspaceBreadcrumb */
  breadcrumbs: PropTypes.arrayOf(
    PropTypes.shape({
      label: PropTypes.string.isRequired,
      href: PropTypes.string,
      icon: PropTypes.elementType
    })
  ),

  /** Pre-built Avatar node for header Row 1 */
  avatar: PropTypes.node,

  /** Title text for header Row 1 */
  title: PropTypes.string,

  /** If provided, title becomes editable via EditableField. Signature: (fieldKey, newValue) => Promise<boolean> */
  onTitleSave: PropTypes.func,

  /** Disable title editing (only relevant when onTitleSave is provided) */
  titleDisabled: PropTypes.bool,

  /** Actions node rendered top-right of header (e.g. IconButton + Menu) */
  headerActions: PropTypes.node,

  /** Array of Chip nodes for header Row 2 */
  chips: PropTypes.arrayOf(PropTypes.node),

  /** Extra row nodes rendered between chips and divider */
  extraRows: PropTypes.arrayOf(PropTypes.node),

  /** Array of info item nodes after divider */
  infoItems: PropTypes.arrayOf(PropTypes.node),

  /** Tab definitions */
 tabs: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      label: PropTypes.node.isRequired,
      disabled: PropTypes.bool
    })
  ),

  /** Currently active tab id */
  activeTab: PropTypes.string,

  /** Tab change callback: (newTabId) => void */
  onTabChange: PropTypes.func,

  /** Show loading skeleton */
  loading: PropTypes.bool,

  /** Tab content */
  children: PropTypes.node
};