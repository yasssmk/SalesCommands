// frontend/src/views/admin/accounts/list.jsx

'use client';
import { useMemo, useState, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Checkbox from '@mui/material/Checkbox';

// project imports
import IconButton from 'components/@extended/IconButton';
import ReusableTable from 'components/table/Table';
import AccountModal from 'sections/admin/accounts/AccountModal';
import AlertAccountDelete from 'sections/admin/accounts/AlertAccountDelete';
import AlertAccountBulkDelete from 'sections/admin/accounts/AlertAccountBulkDelete';

// hooks
import useLocalStorage from 'hooks/useLocalStorage';
import { useAuth } from 'hooks/useAuth';

// api
import { useGetAccounts } from 'api/admin/accounts';
import { tenantKey } from 'api/_swr';

// utils
import { formatDateTime } from 'config/formatters';

// assets
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';

// ==============================|| SORT FIELD MAPPING ||============================== //

/**
 * Map frontend column IDs to backend field names for sorting
 * Critical for server-side sorting to work correctly
 */
const COLUMN_TO_BACKEND_FIELD = {
  company_name: 'company_name',
  country: 'country',
  type: 'type',
  classification: 'classification',
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

// ==============================|| ACCOUNTS LIST PAGE ||============================== //

/**
 * Account Management List Page
 * 
 * Main container page that orchestrates all account management components.
 * Follows the same architectural pattern as User Management for consistency.
 * 
 * Architecture:
 * - Uses ReusableTable component directly (no wrapper)
 * - Columns defined in this file with useMemo
 * - All state management (pagination, search, sorting, selection) handled here
 * - Bulk selection enabled
 */
export default function AccountsListPage() {
  const { tenantId } = useAuth();

  const MAX_PAGE_SIZE = 100;

  // ==============================|| STATE MANAGEMENT ||============================== //

  // Pagination state with localStorage persistence
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('accountTablePageSize', 10);

  const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 10;
    return Math.min(parsed, MAX_PAGE_SIZE);
  }, [pageSize]);

  // Search state
  const [search, setSearch] = useState('');

  // Sorting state (TanStack Table format)
  const [sorting, setSorting] = useState([]);

  // Selection state for bulk operations
  const [selectedRows, setSelectedRows] = useState(new Set());

  // Modal states
  const [accountModal, setAccountModal] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [deleteModal, setDeleteModal] = useState(false);
  const [accountToDelete, setAccountToDelete] = useState(null);
  const [bulkDeleteModal, setBulkDeleteModal] = useState(false);

  // ==============================|| COMPUTE ORDERING STRING ||============================== //

  /**
   * Convert TanStack sorting to Django ordering format
   * Example: [{id: 'company_name', desc: true}] → '-company_name'
   */
  const ordering = useMemo(() => {
    if (!sorting || !Array.isArray(sorting) || sorting.length === 0) {
      return '';
    }

    return sorting
      .map(({ id, desc }) => {
        const backendField = COLUMN_TO_BACKEND_FIELD[id] || id;
        return desc ? `-${backendField}` : backendField;
      })
      .join(',');
  }, [sorting]);

  // ==============================|| API DATA FETCHING ||============================== //

  const _accountsHook = useGetAccounts({
    page,
    pageSize: validPageSize,
    search,
    ordering
  }) || {};

  const {
    accountsLoading = false,
    accounts = [],
    accountsCount = 0,
    accountsError = null
  } = _accountsHook;

  // Build SWR key for cache revalidation
  const swrKey = useMemo(() => {
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('page_size', validPageSize);
    if (search) params.append('search', search);
    if (ordering) params.append('ordering', ordering);
    const url = `/company-accounts/${params.toString() ? `?${params.toString()}` : ''}`;
    return tenantKey(url, tenantId);
  }, [page, validPageSize, search, ordering, tenantId]);

  // ==============================|| SELECTION HANDLERS ||============================== //

  const handleSelectRow = useCallback((accountId) => {
    setSelectedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(accountId)) {
        newSet.delete(accountId);
      } else {
        newSet.add(accountId);
      }
      return newSet;
    });
  }, []);

  const handleSelectAll = useCallback((e) => {
    e.stopPropagation();
    if (e.target.checked && accounts) {
      setSelectedRows(new Set(accounts.map((account) => account.id)));
    } else {
      setSelectedRows(new Set());
    }
  }, [accounts]);

  const allSelected = accounts && accounts.length > 0 && selectedRows.size === accounts.length;
  const someSelected = selectedRows.size > 0 && selectedRows.size < (accounts?.length || 0);

  // ==============================|| PAGINATION/SEARCH/SORT HANDLERS ||============================== //

  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newPageSize }) => {
      setPage(newPage);

      const size = Number(newPageSize);
      if (!isNaN(size) && size > 0 && size !== validPageSize) {
        setPageSize(size);
      }
    },
    [setPageSize, validPageSize]
  );

  const handleSearchChange = useCallback((searchTerm) => {
    setSearch(searchTerm);
    setPage(1);
  }, []);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prevSorting) => {
      const newSorting = typeof updaterOrValue === 'function'
        ? updaterOrValue(prevSorting)
        : updaterOrValue;

      if (JSON.stringify(newSorting) !== JSON.stringify(prevSorting)) {
        setPage(1);
      }

      return newSorting;
    });
  }, []);

  // ==============================|| MODAL HANDLERS ||============================== //

  const handleAddAccount = useCallback(() => {
    setSelectedAccount(null);
    setAccountModal(true);
  }, []);

  const handleEditAccount = useCallback((account) => {
    setSelectedAccount(account);
    setAccountModal(true);
  }, []);

  const handleDeleteAccount = useCallback((account) => {
    setAccountToDelete(account);
    setDeleteModal(true);
  }, []);

  const handleOpenDeleteDialog = useCallback((account) => {
    setAccountToDelete(account);
    setDeleteModal(true);
  }, []);

  const handleCloseDeleteDialog = useCallback(() => {
    setDeleteModal(false);
    setAccountToDelete(null);
  }, []);

  const handleBulkDeleteComplete = useCallback(() => {
    setSelectedRows(new Set());
  }, []);

  // ==============================|| COLUMNS DEFINITION ||============================== //

  const columns = useMemo(
    () => [
      // Selection checkbox column
      {
        id: 'select',
        enableSorting: false,
        header: () => (
          <div onClick={(e) => e.stopPropagation()}>
            <Checkbox
              checked={allSelected}
              indeterminate={someSelected}
              onChange={handleSelectAll}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        ),
        cell: ({ row }) => {
          const isSelected = selectedRows.has(row.original.id);
          return (
            <div onClick={(e) => e.stopPropagation()}>
              <Checkbox
                checked={isSelected}
                onChange={(e) => {
                  e.stopPropagation();
                  handleSelectRow(row.original.id);
                }}
                onClick={(e) => e.stopPropagation()}
              />
            </div>
          );
        }
      },
      // Company Name
      {
        header: 'Company Name',
        accessorKey: 'company_name',
        cell: ({ getValue }) => (
          <Typography variant="subtitle1">
            {getValue() || 'N/A'}
          </Typography>
        )
      },
      // Country
      {
        header: 'Country',
        accessorKey: 'country',
        cell: ({ getValue }) => (
          <Typography variant="body2">
            {getValue() || '-'}
          </Typography>
        )
      },
      // Type
      {
        header: 'Type',
        accessorKey: 'type',
        cell: ({ getValue }) => {
          const type = getValue();
          return type ? (
            <Chip
              label={type}
              color={TYPE_COLORS[type] || 'default'}
              size="small"
              variant="light"
            />
          ) : (
            <Typography variant="body2" color="text.secondary">-</Typography>
          );
        }
      },
      // Classification
      {
        header: 'Classification',
        accessorKey: 'classification',
        cell: ({ getValue }) => {
          const classification = getValue();
          return classification ? (
            <Chip
              label={classification}
              color={CLASSIFICATION_COLORS[classification] || 'default'}
              size="small"
              variant="outlined"
            />
          ) : (
            <Typography variant="body2" color="text.secondary">-</Typography>
          );
        }
      },
      // Account Owner
      {
        header: 'Account Owner',
        accessorKey: 'account_owner',
        cell: ({ row }) => {
          const owner = row.original.account_owner;
          if (!owner) {
            return <Typography variant="body2" color="text.secondary">Unassigned</Typography>;
          }
          const name = owner.name || `${owner.first_name || ''} ${owner.last_name || ''}`.trim();
          return (
            <Typography variant="body2">
              {name || owner.email || 'Unknown'}
            </Typography>
          );
        }
      },
      // Last Update
      {
        header: 'Last Update',
        accessorKey: 'updated_at',
        cell: ({ getValue }) => {
          const v = getValue();
          return (
            <Typography variant="body2" color="text.secondary">
              {v ? formatDateTime(v) : 'Never'}
            </Typography>
          );
        }
      },
      // Actions
      {
        header: 'Actions',
        id: 'actions',
        meta: { className: 'cell-center' },
        disableSortBy: true,
        enableSorting: false,
        cell: ({ row }) => (
          <Stack direction="row" alignItems="center" justifyContent="center" spacing={0}>
            <Tooltip title="Edit">
              <IconButton
                color="primary"
                onClick={(e) => {
                  e.stopPropagation();
                  handleEditAccount(row.original);
                }}
              >
                <EditOutlined />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete">
              <IconButton
                color="error"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteAccount(row.original);
                }}
              >
                <DeleteOutlined />
              </IconButton>
            </Tooltip>
          </Stack>
        )
      }
    ],
    [allSelected, someSelected, handleSelectAll, selectedRows, handleSelectRow, handleEditAccount, handleDeleteAccount]
  );

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <ReusableTable
        data={accounts}
        columns={columns}
        loading={accountsLoading}
        error={accountsError}
        swrKey={swrKey}
        modalToggler={handleAddAccount}
        totalCount={accountsCount}
        currentPage={page}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        initialPageSize={validPageSize}
        selectedCount={selectedRows.size}
        selectedRows={selectedRows}
        onEdit={() => {
          if (selectedRows.size === 1) {
            const accountId = Array.from(selectedRows)[0];
            const account = accounts.find(a => a.id === accountId);
            if (account) {
              handleEditAccount(account);
            }
          }
        }}
        onDelete={() => {
          if (selectedRows.size === 1) {
            const accountId = Array.from(selectedRows)[0];
            const account = accounts.find(a => a.id === accountId);
            if (account) {
              handleOpenDeleteDialog(account);
            }
          } else if (selectedRows.size > 1) {
            setBulkDeleteModal(true);
          }
        }}
        // Customization
        addButtonLabel="Add Account"
        addButtonTooltip="Add Account"
        searchPlaceholder={`Search ${accountsCount} accounts...`}
        exportFilename="accounts-list.csv"
        emptyMessage="No accounts found"
        emptyDescription="Start by adding your first company account"
      />

      {/* Account Modal (Add/Edit) */}
      <AccountModal
        open={accountModal}
        modalToggler={setAccountModal}
        account={selectedAccount}
      />

      {/* Single Delete Confirmation */}
      <AlertAccountDelete
        account={accountToDelete}
        open={deleteModal}
        handleClose={handleCloseDeleteDialog}
      />

      {/* Bulk Delete Confirmation */}
      <AlertAccountBulkDelete
        selectedIds={Array.from(selectedRows)}
        open={bulkDeleteModal}
        handleClose={() => setBulkDeleteModal(false)}
        onDeleteComplete={handleBulkDeleteComplete}
      />
    </>
  );
}