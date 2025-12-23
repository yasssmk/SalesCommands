// frontend/src/sections/territories/workspace/TerritoryAccountsTab.jsx

'use client';

import PropTypes from 'prop-types';
import { useMemo, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';

// material-ui
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// project imports
import IconButton from 'components/@extended/IconButton';
import ReusableTable from 'components/table/Table';

// hooks
import useLocalStorage from 'hooks/useLocalStorage';
import { useAuth } from 'hooks/useAuth';

// api
import { useGetAccounts } from 'api/admin/accounts';
import { tenantKey } from 'api/_swr';

// assets
import ArrowRightOutlined from '@ant-design/icons/ArrowRightOutlined';

// ==============================|| SORT FIELD MAPPING ||============================== //

const COLUMN_TO_BACKEND_FIELD = {
  company_name: 'company_name',
  type: 'type',
  classification: 'classification',
  industry: 'industry',
  account_owner: 'account_owner__last_name',
  updated_at: 'updated_at'
};

// ==============================|| TYPE/CLASSIFICATION COLORS ||============================== //

const TYPE_COLORS = {
  CLIENT: 'success',
  PROSPECT: 'warning',
  PARTNER: 'info',
  VENDOR: 'secondary',
  OTHER: 'default'
};

const CLASSIFICATION_COLORS = {
  ENTERPRISE: 'primary',
  MIDMARKET: 'info',
  SMB: 'success',
  STARTUP: 'warning',
  NONPROFIT: 'secondary'
};

// ==============================|| TERRITORY ACCOUNTS TAB ||============================== //

/**
 * TerritoryAccountsTab Component
 * 
 * Displays accounts belonging to a territory.
 * Read-only list with navigation to account workspace.
 * 
 * @param {Object} props
 * @param {string} props.territoryId - UUID of the territory
 * @param {Object} props.territory - Territory data
 */
export default function TerritoryAccountsTab({ territoryId, territory }) {
  const { tenantId } = useAuth();
  const router = useRouter();

  // ==============================|| PAGINATION STATE ||============================== //

  const [pageSize, setPageSize] = useLocalStorage('territoryAccountsPageSize', 25);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sorting, setSorting] = useState([{ id: 'company_name', desc: false }]);

  // Validate page size
  const validPageSize = useMemo(() => {
    const size = Number(pageSize);
    return [10, 25, 50, 100].includes(size) ? size : 25;
  }, [pageSize]);

  // Build ordering string
  const ordering = useMemo(() => {
    if (!sorting.length) return 'company_name';
    const sort = sorting[0];
    const backendField = COLUMN_TO_BACKEND_FIELD[sort.id] || sort.id;
    return sort.desc ? `-${backendField}` : backendField;
  }, [sorting]);

  // ==============================|| DATA FETCHING ||============================== //

  const swrKey = tenantKey('territory-accounts', tenantId);

  const {
    accounts,
    accountsCount,
    accountsLoading,
    accountsError
  } = useGetAccounts({
    page,
    pageSize: validPageSize,
    search,
    ordering,
    filters: {
      territory_id: territoryId
    }
  });

  // ==============================|| HANDLERS ||============================== //

  const handlePaginationChange = useCallback((newPage, newPageSize) => {
    if (newPageSize !== validPageSize) {
      setPageSize(newPageSize);
      setPage(1);
    } else {
      setPage(newPage);
    }
  }, [validPageSize, setPageSize]);

  const handleSearchChange = useCallback((value) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting(prev => {
      return typeof updaterOrValue === 'function'
        ? updaterOrValue(prev)
        : updaterOrValue;
    });
  }, []);

  const handleRowClick = useCallback((account) => {
    router.push(`/accounts/${account.id}`);
  }, [router]);

  // ==============================|| COLUMNS DEFINITION ||============================== //

  const columns = useMemo(
    () => [
      // Company Name
      {
        header: 'Company',
        id: 'company_name',
        accessorKey: 'company_name',
        cell: ({ row }) => {
          const account = row.original;
          return (
            <Stack spacing={0}>
              <Typography variant="subtitle2" fontWeight={600}>
                {account.company_name}
              </Typography>
              {account.city && account.country && (
                <Typography variant="caption" color="text.secondary">
                  {account.city}, {account.country}
                </Typography>
              )}
            </Stack>
          );
        }
      },
      // Type
      {
        header: 'Type',
        id: 'type',
        accessorKey: 'type',
        cell: ({ row }) => {
          const value = row.original.type;
          if (!value) {
            return <Typography variant="body2" color="text.disabled">—</Typography>;
          }
          return (
            <Chip
              label={row.original.type_display || value}
              size="small"
              color={TYPE_COLORS[value] || 'default'}
              variant="light"
            />
          );
        }
      },
      // Classification
      {
        header: 'Classification',
        id: 'classification',
        accessorKey: 'classification',
        cell: ({ row }) => {
          const value = row.original.classification;
          if (!value) {
            return <Typography variant="body2" color="text.disabled">—</Typography>;
          }
          return (
            <Chip
              label={row.original.classification_display || value}
              size="small"
              color={CLASSIFICATION_COLORS[value] || 'default'}
              variant="outlined"
            />
          );
        }
      },
      // Industry
      {
        header: 'Industry',
        id: 'industry',
        accessorKey: 'industry',
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2">{value}</Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">—</Typography>
          );
        }
      },
      // Account Owner
      {
        header: 'Owner',
        id: 'account_owner',
        accessorKey: 'account_owner',
        cell: ({ row }) => {
          const owner = row.original.account_owner;
          if (!owner) {
            return <Typography variant="body2" color="text.disabled">—</Typography>;
          }
          return (
            <Typography variant="body2">
              {owner.full_name || owner.email}
            </Typography>
          );
        }
      },
      // Actions
      {
        header: '',
        id: 'actions',
        meta: { className: 'cell-center' },
        disableSortBy: true,
        enableSorting: false,
        cell: ({ row }) => (
          <Tooltip title="Open Account">
            <IconButton
              color="primary"
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                handleRowClick(row.original);
              }}
            >
              <ArrowRightOutlined />
            </IconButton>
          </Tooltip>
        )
      }
    ],
    [handleRowClick]
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <ReusableTable
        data={accounts}
        columns={columns}
        loading={accountsLoading}
        error={accountsError}
        swrKey={swrKey}
        totalCount={accountsCount}
        currentPage={page}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        initialPageSize={validPageSize}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        searchPlaceholder={`Search ${accountsCount || 0} accounts...`}
        emptyMessage="No accounts in this territory"
        emptyDescription="Adjust territory filters or check account assignments"
        onRowClick={handleRowClick}
        // No add/edit/delete - read only
        modalToggler={null}
        enableImport={false}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

TerritoryAccountsTab.propTypes = {
  territoryId: PropTypes.string.isRequired,
  territory: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    filter_definition: PropTypes.object
  })
};