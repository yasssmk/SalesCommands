// frontend/src/views/accounts/decisionSteps/index.jsx
/**
 * Decision Step Workspace Page
 *
 * Uses WorkspaceLayout for standardized header/tabs/content structure.
 * Header Row 3: Account name + Cycle name (same pattern as Activity header).
 */

'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';

// MUI
import { useTheme } from '@mui/material/styles';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Project imports
import WorkspaceLayout from 'components/WorkspaceLayout';
import { useGetDecisionStep, PIPELINE_STEP_LABELS } from 'api/accounts/decisionCycles';
import { useGetAccount } from 'api/admin/accounts';
import { buildStepBreadcrumbs } from 'components/WorkspaceBreadcrumb';

// Tab config (reuse existing constants)
import { DECISION_STEP_TABS, DEFAULT_TAB } from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepTabs';

// Tab content components
import DecisionStepOverviewTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepOverviewTab';
import DecisionStepActivitiesTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepActivitiesTab';
import DecisionStepContactsTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepContactsTab';
import DecisionStepSignalsTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepSignalsTab';
import DecisionStepAIPrepTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepAIPrepTab';

// Icons
import {
  SearchOutlined,
  ToolOutlined,
  SolutionOutlined,
  DollarOutlined,
  FileProtectOutlined,
  SettingOutlined,
  RocketOutlined,
  BankOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';

// ==============================|| STAGE CONFIGURATION ||============================== //

const STAGE_ICONS = {
  QUALIFICATION: SearchOutlined,
  TECHNICAL_FIT: ToolOutlined,
  SOLUTION_VALIDATION: SolutionOutlined,
  BUSINESS_CASE: DollarOutlined,
  CLOSING: FileProtectOutlined,
  IMPLEMENTATION: SettingOutlined,
  GO_LIVE: RocketOutlined
};

const STAGE_AVATAR_COLORS = {
  QUALIFICATION: 'info.main',
  TECHNICAL_FIT: 'secondary.main',
  SOLUTION_VALIDATION: 'success.main',
  BUSINESS_CASE: 'warning.main',
  CLOSING: 'primary.main',
  IMPLEMENTATION: 'grey.500',
  GO_LIVE: 'success.dark'
};

const STATUS_CONFIG = {
  WON: { label: 'Won', color: 'primary' },
  REJECTED: { label: 'Rejected', color: 'error' },
  OVERDUE: { label: 'Overdue', color: 'error' },
  VALIDATED: { label: 'Validated', color: 'primary' },
  IN_PROGRESS: { label: 'In Progress', color: 'secondary' },
  ON_HOLD: { label: 'On Hold', color: 'warning' },
  IN_CHASING: { label: 'In Chasing', color: 'warning' },
  NOT_STARTED: { label: 'Not Started', color: 'default' }
};

// ==============================|| DECISION STEP WORKSPACE PAGE ||============================== //

export default function DecisionStepWorkspacePage() {
  const theme = useTheme();
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Extract route params
  const accountId = params?.id;
  const stepId = params?.stepId;
  const currentTab = searchParams.get('tab') || DEFAULT_TAB;

  // Fetch data
  const { step, stepLoading, stepError, mutateStep } = useGetDecisionStep(stepId);
  const { account, accountLoading } = useGetAccount(accountId);

  // Derived data
  const cycleId = step?.cycle_id || step?.cycle;
  const cycleName = step?.cycle_detail?.name || step?.cycle_name || null;
  const isLoading = stepLoading || accountLoading;

  // ==============================|| HANDLERS ||============================== //

  const handleTabChange = (newTab) => {
    const urlParams = new URLSearchParams(searchParams.toString());
    urlParams.set('tab', newTab);
    router.push(`?${urlParams.toString()}`, { scroll: false });
  };

  const handleAccountClick = () => {
    if (accountId) {
      router.push(`/accounts/${accountId}?tab=decision-cycle`);
    }
  };

  const handleCycleClick = () => {
    if (accountId) {
      router.push(`/accounts/${accountId}?tab=decision-cycle`);
    }
  };

  // ==============================|| ERROR STATE ||============================== //

  if (!isLoading && (stepError || !step)) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <Stack spacing={2} alignItems="center">
          <Typography color="error">Decision step not found</Typography>
          <Button variant="outlined" onClick={() => router.back()}>
            Go Back
          </Button>
        </Stack>
      </Box>
    );
  }

  // ==============================|| HEADER PROPS (derived from step) ||============================== //

  const StageIcon = STAGE_ICONS[step?.stage] || SearchOutlined;
  const avatarColor = STAGE_AVATAR_COLORS[step?.stage] || 'grey.500';
  const statusConfig = STATUS_CONFIG[step?.derived_status] || STATUS_CONFIG.NOT_STARTED;
  const stepName = step?.name || PIPELINE_STEP_LABELS?.[step?.stage] || step?.stage || '';
  const accountName = account?.company_name;

  // Breadcrumbs
  const breadcrumbItems = step ? buildStepBreadcrumbs({
    accountId,
    accountName,
    cycleName,
    stepName
  }) : [];

  // Avatar node
  const avatarNode = (
    <Avatar
      sx={{
        width: 56,
        height: 56,
        bgcolor: avatarColor,
        fontSize: '1.5rem'
      }}
    >
      <StageIcon />
    </Avatar>
  );

  // Chips (Row 2)
  const chips = [
    <Chip
      key="status"
      label={step?.derived_status_display || statusConfig.label}
      color={statusConfig.color}
      size="small"
      variant="filled"
    />
  ];

  // Info items (Row 3): Account name + Cycle name only
  const infoItems = [
    // Account (clickable)
    accountName && (
      <Stack
        key="account"
        direction="row"
        spacing={0.75}
        alignItems="center"
        onClick={handleAccountClick}
        sx={{
          cursor: 'pointer',
          '&:hover .info-link': { textDecoration: 'underline' }
        }}
      >
        <BankOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.text.secondary, display: 'flex' }} />
        <Typography variant="body2" color="primary.main" className="info-link">
          {accountName}
        </Typography>
      </Stack>
    ),

    // Cycle (clickable, with ApartmentOutlined — same as Activity header origin)
    cycleName && (
      <Stack
        key="cycle"
        direction="row"
        spacing={0.75}
        alignItems="center"
        onClick={handleCycleClick}
        sx={{
          cursor: 'pointer',
          '&:hover .info-link': { textDecoration: 'underline' }
        }}
      >
        <ApartmentOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.text.secondary, display: 'flex' }} />
        <Typography variant="body2" color="primary.main" className="info-link">
          {cycleName}
        </Typography>
      </Stack>
    )
  ];

  // ==============================|| TAB CONTENT ||============================== //

  const renderTabContent = () => {
    switch (currentTab) {
      case 'overview':
        return (
          <DecisionStepOverviewTab
            step={step}
            account={account}
            onUpdate={mutateStep}
          />
        );
      case 'activities':
        return (
          <DecisionStepActivitiesTab
            step={step}
            accountId={accountId}
            onUpdate={mutateStep}
          />
        );
      case 'contacts':
        return (
          <DecisionStepContactsTab
            step={step}
            accountId={accountId}
          />
        );
      case 'signals':
        return <DecisionStepSignalsTab step={step} />;
      case 'ai-prep':
        return <DecisionStepAIPrepTab step={step} />;
      default:
        return (
          <DecisionStepOverviewTab
            step={step}
            account={account}
            onUpdate={mutateStep}
          />
        );
    }
  };

  // ==============================|| RENDER ||============================== //

  return (
    <WorkspaceLayout
      breadcrumbs={breadcrumbItems}
      avatar={avatarNode}
      title={stepName}
      chips={chips}
      infoItems={infoItems}
      tabs={DECISION_STEP_TABS}
      activeTab={currentTab}
      onTabChange={handleTabChange}
      loading={isLoading}
    >
      {renderTabContent()}
    </WorkspaceLayout>
  );
}