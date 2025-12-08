// frontend/src/views/territories/list.jsx

'use client';

import { useMemo, useState, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import ReusableTable from 'components/table/Table';
import TerritorySelector from 'sections/territories/TerritorySelector';

// hooks
import { useAuth } from 'hooks/useAuth';

// api
import { useGetAccounts } from 'api/admin/accounts';
import { TERRITORIES, DEFAULT_TERRITORY_ID } from 'api/territories';

// ==============================|| TERRITORIES LIST PAGE ||============================== //

/**
 * Territories Page - Sales-facing workspace
 * 
 * NOT an admin CRUD page. This is a read-only exploration interface
 * for sales reps to view and filter account segments.
 * 
 * Phase 1: Hardcoded territories (All Accounts, All Contacts)
 * Future: Backend API for territory CRUD
 */
export default function TerritoriesListPage() {
  const { tenantId } = useAuth();

  // ==============================|| STATE ||============================== //

  const [selectedTerritoryId, setSelectedTerritoryId] = useState(DEFAULT_TERRITORY_ID);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState('');
  const [sorting, setSorting] = useState([]);

  // Get selected territory data
  const selectedTerritory = useMemo(() => {
    return TERRITORIES.find(t => t.id === selectedTerritoryId) || TERRITORIES[0];
  }, [selectedTerritoryId]);


  // ==============================|| API DATA ||============================== //

  // Only fetch accounts if territory type is 'account'
  const shouldFetchAccounts = selectedTerritory?.type === 'account';

  const {
    accounts = [],
    accountsCount = 0,
    accountsLoading = false,
    accountsError = null
  } = useGetAccounts(shouldFetchAccounts ? { page, pageSize, search } : null) || {};

  // For contacts territory - placeholder until Contacts API exists
  const isContactsTerritory = selectedTerritory?.type === 'contact';

  // ==============================|| HANDLERS ||============================== //

  const handleTerritoryChange = useCallback((territoryId) => {
    setSelectedTerritoryId(territoryId);
    setPage(1);
    setSearch('');
  }, []);

  const handlePaginationChange = useCallback(({ page: newPage, pageSize: newPageSize }) => {
    setPage(newPage);
    if (newPageSize !== pageSize) {
      setPageSize(newPageSize);
    }
  }, [pageSize]);

  const handleSearchChange = useCallback((searchTerm) => {
    setSearch(searchTerm);
    setPage(1);
  }, []);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prev) => 
      typeof updaterOrValue === 'function' ? updaterOrValue(prev) : updaterOrValue
    );
  }, []);

  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(() => [
    {
      header: 'Company',
      accessorKey: 'company_name',
      cell: ({ row }) => {
        const { company_name, industry, city, country, website } = row.original;
        
        // Generate favicon URL from website domain
        let faviconUrl = null;
        if (website) {
          try {
            const domain = new URL(website.startsWith('http') ? website : `https://${website}`).hostname;
            faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;
          } catch (e) {
            // Invalid URL, no favicon
          }
        }
        
        const location = [city, country].filter(Boolean).join(', ');
        
        return (
          <Stack direction="row" spacing={1.5} alignItems="center">
            {/* Logo */}
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: 1,
                bgcolor: 'grey.100',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                overflow: 'hidden'
              }}
            >
              {faviconUrl ? (
                <Box
                  component="img"
                  src={faviconUrl}
                  alt=""
                  sx={{ width: 24, height: 24 }}
                  onError={(e) => {
                    e.target.style.display = 'none';
                  }}
                />
              ) : (
                <Typography variant="caption" color="text.secondary">
                  {company_name?.charAt(0)?.toUpperCase() || '?'}
                </Typography>
              )}
            </Box>
            
            {/* Company info */}
            <Stack spacing={0}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                  {company_name || '—'}
                </Typography>
                {location && (
                  <Typography variant="body2" color="text.secondary">
                    {location}
                  </Typography>
                )}
              </Stack>
              {industry && (
                <Typography variant="caption" color="text.secondary">
                  {industry}
                </Typography>
              )}
            </Stack>
          </Stack>
        );
      }
    },
    {
      header: 'Type',
      accessorKey: 'type',
      cell: ({ getValue }) => {
        const value = getValue();
        if (!value) return '—';
        
        const colorMap = {
          CLIENT: 'success',
          PROSPECT: 'warning',
          PARTNER: 'info',
          VENDOR: 'secondary',
          OTHER: 'default'
        };
        
        return (
          <Chip
            label={value}
            color={colorMap[value] || 'default'}
            size="small"
            variant="light"
          />
        );
      }
    },
    {
      header: 'Classification',
      accessorKey: 'classification',
      cell: ({ getValue }) => {
        const value = getValue();
        return (
          <Typography variant="body2" color="text.secondary">
            {value || '—'}
          </Typography>
        );
      }
    },
    {
      header: 'Owner',
      accessorKey: 'account_owner',
      cell: ({ row }) => {
        const owner = row.original.account_owner;
        if (!owner) return <Typography color="text.secondary">—</Typography>;
        
        const name = `${owner.first_name || ''} ${owner.last_name || ''}`.trim();
        return (
          <Typography variant="body2">
            {name || owner.email || '—'}
          </Typography>
        );
      }
    }
  ], []);

  // ==============================|| RENDER ||============================== //

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      
      {/* ==================== HEADER ==================== */}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h4">Territories</Typography>
      </Stack>


      {/* ==================== TERRITORY SELECTOR ==================== */}
      <MainCard sx={{ p: 2 }}>
        <TerritorySelector
          territories={TERRITORIES}
          selectedId={selectedTerritoryId}
          onChange={handleTerritoryChange}
        />
      </MainCard>

      {/* ==================== SUMMARY PLACEHOLDER ==================== */}
      <MainCard sx={{ p: 2 }}>
        <Stack direction="row" spacing={4}>
          <Box>
            <Typography variant="h3">
              {shouldFetchAccounts ? accountsCount : 0}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {selectedTerritory?.type === 'account' ? 'Accounts' : 'Contacts'}
            </Typography>
          </Box>
        </Stack>
      </MainCard>

      {/* ==================== DATA LIST ==================== */}
      {isContactsTerritory ? (
        <MainCard>
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h5" color="text.secondary">
              Contacts module coming soon
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Contact-based territories will be available once the Contacts API is implemented.
            </Typography>
          </Box>
        </MainCard>
      ) : (
        <MainCard content={false}>
          <ReusableTable
            columns={columns}
            data={accounts}
            totalRows={accountsCount}
            loading={accountsLoading}
            error={accountsError}
            page={page}
            pageSize={pageSize}
            onPaginationChange={handlePaginationChange}
            search={search}
            onSearchChange={handleSearchChange}
            sorting={sorting}
            onSortingChange={handleSortingChange}
            emptyMessage="No accounts found"
            searchPlaceholder="Search accounts..."
          />
        </MainCard>
      )}
    </Box>
  );
}