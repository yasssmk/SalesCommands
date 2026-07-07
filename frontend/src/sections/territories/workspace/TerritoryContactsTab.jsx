// frontend/src/sections/territories/workspace/TerritoryContactsTab.jsx

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
import { useCurrentUser } from 'hooks/useCurrentUser';

// api
import { useGetContacts } from 'api/businessData/contacts';
import { tenantKey } from 'api/_swr';

// assets
import ArrowRightOutlined from '@ant-design/icons/ArrowRightOutlined';

// ==============================|| SORT FIELD MAPPING ||============================== //

const COLUMN_TO_BACKEND_FIELD = {
  full_name: 'last_name',
  email: 'email',
  job_title: 'job_title',
  influence_level: 'influence_level',
  department_name: 'standard_department__name',
  account: 'account__company_name'
};

// ==============================|| INFLUENCE LEVEL COLORS ||============================== //

const INFLUENCE_COLORS = {
  DECISION_MAKER: 'success',
  INFLUENCER: 'info',
  CHAMPION: 'primary',
  USER: 'default',
  GATEKEEPER: 'warning',
  BLOCKER: 'error',
  UNKNOWN: 'default'
};

// ==============================|| TERRITORY CONTACTS TAB ||============================== //

/**
 * TerritoryContactsTab Component
 * 
 * Displays contacts belonging to a territory.
 * Read-only list with navigation to account workspace.
 * 
 * @param {Object} props
 * @param {string} props.territoryId - UUID of the territory
 * @param {Object} props.territory - Territory data
 */
export default function TerritoryContactsTab({ territoryId, territory }) {
  const { tenantId } = useAuth();
  const { currentUser } = useCurrentUser();
  const router = useRouter();

  // ==============================|| PAGINATION STATE ||============================== //

  const [pageSize, setPageSize] = useLocalStorage('territoryContactsPageSize', 25);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sorting, setSorting] = useState([{ id: 'full_name', desc: false }]);

  // Validate page size
  const validPageSize = useMemo(() => {
    const size = Number(pageSize);
    return [10, 25, 50, 100].includes(size) ? size : 25;
  }, [pageSize]);

  // Build ordering string
  const ordering = useMemo(() => {
    if (!sorting.length) return 'last_name';
    const sort = sorting[0];
    const backendField = COLUMN_TO_BACKEND_FIELD[sort.id] || sort.id;
    return sort.desc ? `-${backendField}` : backendField;
  }, [sorting]);

  // ==============================|| DATA FETCHING ||============================== //

  const swrKey = tenantKey('territory-contacts', tenantId);

  // Translate the territory's saved filter_definition into Contact list
  // filters. There is no backend territory_id resolution for contacts, so the
  // segment is reproduced from its filters here (kept in sync with the
  // scope-aware count in _count_contacts_for_territory).
  const contactFilters = useMemo(() => {
    const fd = territory?.filter_definition || {};
    const f = {};

    if (fd.influence_level?.length) {
      f.influence_level = fd.influence_level;
    }
    if (fd.standard_department?.length) {
      f.standard_department = fd.standard_department;
    }
    if (fd.has_buying_authority !== undefined && fd.has_buying_authority !== null) {
      f.has_buying_authority = fd.has_buying_authority;
    }

    // "Company's Owner" scope. 'mine' -> contacts whose company account is
    // owned by the current user. 'team' is not expressible as a simple FK
    // filter yet (see TECH_DEBT) and currently lists unscoped.
    if (fd.contact_scope === 'mine' && currentUser?.id) {
      f.account_owner_id = currentUser.id;
    }

    return f;
  }, [territory?.filter_definition, currentUser?.id]);

  const {
    contacts,
    contactsCount,
    contactsLoading,
    contactsError
  } = useGetContacts({
    page,
    pageSize: validPageSize,
    search,
    ordering,
    filters: contactFilters
  });

  // ==============================|| HANDLERS ||============================== //

  const handlePaginationChange = useCallback(({ page: newPage, pageSize: newPageSize }) => {
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

  const handleRowClick = useCallback((contact) => {
    // Navigate to account workspace with contacts tab
    if (contact.account?.id) {
      router.push(`/accounts/${contact.account.id}?tab=contacts`);
    }
  }, [router]);

  // ==============================|| COLUMNS DEFINITION ||============================== //

  const columns = useMemo(
    () => [
      // Full Name
      {
        header: 'Name',
        id: 'full_name',
        accessorKey: 'full_name',
        cell: ({ row }) => {
          const contact = row.original;
          const fullName = contact.full_name || `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
          return (
            <Stack spacing={0}>
              <Typography variant="subtitle2" fontWeight={600}>
                {fullName || 'Unknown'}
              </Typography>
              {contact.job_title && (
                <Typography variant="caption" color="text.secondary">
                  {contact.job_title}
                </Typography>
              )}
            </Stack>
          );
        }
      },
      // Account
      {
        header: 'Account',
        id: 'account',
        accessorKey: 'account',
        cell: ({ row }) => {
          const account = row.original.account;
          return account ? (
            <Typography variant="body2">{account.company_name}</Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">—</Typography>
          );
        }
      },
      // Email
      {
        header: 'Email',
        id: 'email',
        accessorKey: 'email',
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2">{value}</Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">—</Typography>
          );
        }
      },
      // Influence Level
      {
        header: 'Influence',
        id: 'influence_level',
        accessorKey: 'influence_level',
        cell: ({ row }) => {
          const value = row.original.influence_level;
          const display = row.original.influence_level_display;
          if (!value || value === 'UNKNOWN') {
            return <Typography variant="body2" color="text.disabled">—</Typography>;
          }
          return (
            <Chip
              label={display || value}
              size="small"
              color={INFLUENCE_COLORS[value] || 'default'}
              variant="light"
            />
          );
        }
      },
      // Department
      {
        header: 'Department',
        id: 'department_name',
        accessorKey: 'department_name',
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2">{value}</Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">—</Typography>
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
          <Tooltip title="View in Account">
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
        data={contacts}
        columns={columns}
        loading={contactsLoading}
        error={contactsError}
        swrKey={swrKey}
        totalCount={contactsCount}
        currentPage={page}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        initialPageSize={validPageSize}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        searchPlaceholder={`Search ${contactsCount || 0} contacts...`}
        emptyMessage="No contacts in this territory"
        emptyDescription="Adjust territory filters to include contacts"
        onRowClick={handleRowClick}
        // No add/edit/delete - read only
        modalToggler={null}
        enableImport={false}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

TerritoryContactsTab.propTypes = {
  territoryId: PropTypes.string.isRequired,
  territory: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    filter_definition: PropTypes.object
  })
};