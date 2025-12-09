// frontend/src/views/territories/list.jsx

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
import TerritoryCard from 'sections/territories/TerritoryCard';

// api
import { TERRITORIES } from 'api/territories';
import { useGetAccounts } from 'api/admin/accounts';

// assets
import PlusOutlined from '@ant-design/icons/PlusOutlined';

// ==============================|| TERRITORIES LIST PAGE ||============================== //

/**
 * Territories Page - Sales-facing workspace
 * 
 * Displays territories as cards for easy navigation.
 * Each card shows count and allows exploring accounts.
 * 
 * Phase 1: Hardcoded territories (All Accounts, All Contacts)
 * Future: Backend API for territory CRUD
 */
export default function TerritoriesListPage() {
  const matchDownSM = useMediaQuery((theme) => theme.breakpoints.down('sm'));

  // ==============================|| STATE ||============================== //

  const [globalFilter, setGlobalFilter] = useState('');
  const [page, setPage] = useState(1);

  // ==============================|| PAGINATION CONFIG ||============================== //

  const PER_PAGE = 6;

  // ==============================|| API DATA - ACCOUNTS COUNT ||============================== //

  // Fetch total accounts count for "All Accounts" territory
  const { accountsCount = 0, accountsLoading } = useGetAccounts({ 
    page: 1, 
    pageSize: 1 
  }) || {};

  // ==============================|| FILTERED TERRITORIES ||============================== //

  const filteredTerritories = useMemo(() => {
    if (!globalFilter) {
      return TERRITORIES;
    }

    const searchLower = globalFilter.toLowerCase();
    return TERRITORIES.filter((territory) => {
      return (
        territory.name.toLowerCase().includes(searchLower) ||
        territory.description?.toLowerCase().includes(searchLower)
      );
    });
  }, [globalFilter]);

  // ==============================|| PAGINATION ||============================== //

  const totalPages = Math.ceil(filteredTerritories.length / PER_PAGE);

  const paginatedTerritories = useMemo(() => {
    const startIndex = (page - 1) * PER_PAGE;
    const endIndex = startIndex + PER_PAGE;
    return filteredTerritories.slice(startIndex, endIndex);
  }, [filteredTerritories, page]);

  // ==============================|| HANDLERS ||============================== //

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleSearchChange = (value) => {
    setGlobalFilter(String(value));
    setPage(1); // Reset to first page on search
  };

  const handleNewTerritory = () => {
    // Future: open create territory modal
    console.log('New territory - coming soon');
  };

  // ==============================|| GET TERRITORY COUNT ||============================== //

  /**
   * Get the record count for a territory
   * Phase 1: Only "All Accounts" has real count
   */
  const getTerritoryCount = (territory) => {
    if (territory.id === 'all-accounts') {
      return accountsCount;
    }
    if (territory.id === 'all-contacts') {
      return 0; // Future: contacts count
    }
    // Future: dynamic count based on filters
    return 0;
  };

  // ==============================|| RENDER ||============================== //

  return (
    <>
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
              placeholder={`Search ${TERRITORIES.length} territories...`}
            />

            {/* Actions */}
            <Stack direction={matchDownSM ? 'column' : 'row'} alignItems="center" spacing={1}>
              <Button 
                variant="contained" 
                startIcon={<PlusOutlined />} 
                onClick={handleNewTerritory}
                disabled
              >
                New Territory
              </Button>
            </Stack>
          </Stack>
        </Stack>
      </Box>

      {/* ==================== TERRITORIES GRID ==================== */}
      <Grid container spacing={3}>
        {paginatedTerritories.length > 0 ? (
          paginatedTerritories.map((territory, index) => (
            <Slide key={territory.id} direction="up" in={true} timeout={50 + index * 50}>
              <Grid item xs={12} sm={6} lg={4}>
                <TerritoryCard
                  territory={territory}
                  accountsCount={getTerritoryCount(territory)}
                  loading={accountsLoading && territory.id === 'all-accounts'}
                />
              </Grid>
            </Slide>
          ))
        ) : (
          <Grid item xs={12}>
            <MainCard>
              <Box sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h5" color="text.secondary">
                  No territories found
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {globalFilter 
                    ? `No territories match "${globalFilter}"`
                    : 'Create your first territory to get started'
                  }
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