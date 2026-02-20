// frontend/src/views/campaigns/list.jsx

'use client';

import { useState, useMemo } from 'react';

// material-ui
import useMediaQuery from '@mui/material/useMediaQuery';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Pagination from '@mui/material/Pagination';
import Slide from '@mui/material/Slide';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import { DebouncedInput } from 'components/third-party/react-table';
import CampaignCard from 'sections/campaigns/CampaignCard';
import OwnerScopeTabs from 'components/filters/OwnerScopeTabs';

// hooks
import useOwnerScope from 'hooks/useOwnerScope';

// api
import { useGetCampaigns } from 'api/campaigns/campaigns';

// assets
import PlusOutlined from '@ant-design/icons/PlusOutlined';

// ==============================|| CAMPAIGNS LIST PAGE ||============================== //

/**
 * Campaigns Page - Sales-facing workspace
 *
 * Displays campaigns as cards for easy navigation.
 * Each card shows type, status, progress, and key metrics.
 *
 * Phase A: Mock data, buttons log to console.
 * Future: Real API, create/edit modals, bulk actions.
 */
export default function CampaignsListPage() {
  const matchDownSM = useMediaQuery((theme) => theme.breakpoints.down('sm'));

  // ==============================|| STATE ||============================== //

  const [globalFilter, setGlobalFilter] = useState('');
  const [page, setPage] = useState(1);

  // Owner scope filter
  const {
    scope: ownerScope,
    setScope: setOwnerScope,
    visibleOptions: ownerScopeOptions,
    apiParams: ownerScopeParams
  } = useOwnerScope({ storageKey: 'campaigns' });

  // ==============================|| PAGINATION CONFIG ||============================== //

  const PER_PAGE = 6;

  // ==============================|| API DATA ||============================== //

  const {
    campaigns = [],
    campaignsCount = 0,
    campaignsLoading,
    campaignsError,
    campaignsEmpty
  } = useGetCampaigns({
    page: 1,
    pageSize: 100,
    search: globalFilter,
    filters: ownerScopeParams
  });

  // ==============================|| PAGINATION ||============================== //

  const totalPages = Math.ceil(campaignsCount / PER_PAGE);

  const paginatedCampaigns = useMemo(() => {
    const startIndex = (page - 1) * PER_PAGE;
    const endIndex = startIndex + PER_PAGE;
    return campaigns.slice(startIndex, endIndex);
  }, [campaigns, page]);

  // ==============================|| HANDLERS ||============================== //

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleSearchChange = (value) => {
    setGlobalFilter(String(value));
    setPage(1);
  };

  const handleNewCampaign = () => {
    console.log('TODO: Open create campaign modal/wizard');
  };

  const handleOpenCampaign = (campaign) => {
    console.log('TODO: Navigate to campaign workspace', campaign.id);
  };

  const handleEditCampaign = (campaign) => {
    console.log('TODO: Open edit campaign modal', campaign.id);
  };

  const handleDeleteCampaign = (campaign) => {
    console.log('TODO: Open delete campaign confirmation', campaign.id);
  };

  // ==============================|| RENDER ||============================== //

  return (
    <>
      {/* ==================== OWNER SCOPE TABS ==================== */}
      <OwnerScopeTabs
        value={ownerScope}
        onChange={setOwnerScope}
        visibleOptions={ownerScopeOptions}
      />

      {/* ==================== HEADER ==================== */}
      <Box sx={{ position: 'relative', marginBottom: 3 }}>
        <Stack direction="row" alignItems="center">
          <Stack
            direction={matchDownSM ? 'column' : 'row'}
            sx={{ width: '100%' }}
            spacing={1}
            justifyContent="space-between"
            alignItems="center"
          >
            {/* Search */}
            <DebouncedInput
              value={globalFilter ?? ''}
              onFilterChange={handleSearchChange}
              placeholder={`Search ${campaignsCount} campaigns...`}
            />

            {/* Actions */}
            <Stack direction={matchDownSM ? 'column' : 'row'} alignItems="center" spacing={1}>
              <Button
                variant="contained"
                startIcon={<PlusOutlined />}
                onClick={handleNewCampaign}
              >
                New Campaign
              </Button>
            </Stack>
          </Stack>
        </Stack>
      </Box>

      {/* ==================== CAMPAIGNS GRID ==================== */}
      <Grid container spacing={3}>
        {paginatedCampaigns.length > 0 ? (
          paginatedCampaigns.map((campaign, index) => (
            <Slide key={campaign.id} direction="up" in={true} timeout={50 + index * 50}>
              <Grid item xs={12} sm={6} lg={4}>
                <CampaignCard
                  campaign={campaign}
                  onOpen={handleOpenCampaign}
                  onEdit={handleEditCampaign}
                  onDelete={handleDeleteCampaign}
                />
              </Grid>
            </Slide>
          ))
        ) : (
          <Grid item xs={12}>
            <MainCard>
              <Box sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h5" color="text.secondary">
                  No campaigns found
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {globalFilter
                    ? `No campaigns match "${globalFilter}"`
                    : 'Create your first campaign to get started'}
                </Typography>
              </Box>
            </MainCard>
          </Grid>
        )}
      </Grid>

      {/* ==================== PAGINATION ==================== */}
      {totalPages > 1 && (
        <Stack spacing={2} sx={{ p: 2.5 }} alignItems="flex-end">
          <Pagination
            sx={{ '& .MuiPaginationItem-root': { my: 0.5 } }}
            count={totalPages}
            size="medium"
            page={page}
            showFirstButton
            showLastButton
            variant="combined"
            color="primary"
            onChange={handlePageChange}
          />
        </Stack>
      )}
    </>
  );
}