// frontend/src/sections/admin/roles/RoleTable.jsx

import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import { useTheme } from '@mui/material/styles';

// ant design icons
import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';

// project imports
import ReusableTable from 'components/table/Table';
import IconButton from 'components/@extended/IconButton';
import TierBadge from './TierBadge';

// utils
import { formatDateTime } from 'config/formatters';

/**
 * RoleTable Component
 * 
 * Wrapper around ReusableTable with role-specific columns and actions.
 * 
 * Columns:
 * 1. Role Name - Text, sortable
 * 2. Tier - Badge with color (Admin/Manager/Individual), sortable
 * 3. Users - Number of users with this role, sortable
 * 4. Created - Creation date, sortable
 * 5. Actions - View/Edit/Delete buttons, non-sortable
 * 
 * @component
 */
function RoleTable({
  data,
  loading,
  error,
  swrKey,
  modalToggler,
  totalCount,
  currentPage,
  onPaginationChange,
  onSearchChange,
  sorting,
  onSortingChange,
  initialPageSize,
  onView,
  onEdit,
  onDelete
}) {
  const theme = useTheme();

  // ==============================|| SORT MAPPING ||============================== //
  
  /**
   * Convert role flags to tier string
   * Backend has is_admin, is_manager, is_individual flags
   * Frontend uses single tier value for simplicity
   */
  // const getTierFromFlags = (role) => {
  //   if (role.is_admin) return 'admin';
  //   if (role.is_manager) return 'manager';
  //   if (role.is_individual) return 'individual';
  //   return 'individual'; // Default fallback
  // };

  const SORT_FIELD_MAP = {
  name: 'name',
  tier: 'tier', 
  users_count: 'users_count',
  created_at: 'created_at'
};

  // ==============================|| COLUMNS DEFINITION ||============================== //

  const columns = useMemo(
    () => [
      // Column 1: Role Name
      {
        header: 'Role Name',
        accessorKey: 'name',
        enableSorting: true,
        cell: ({ getValue }) => (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="subtitle1" fontWeight={500}>
              {getValue() || 'Unnamed Role'}
            </Typography>
          </Stack>
        )
      },

      // Column 2: Tier (with badge)
      {
        header: 'Tier',
        accessorKey: 'tier',
        enableSorting: true,
        cell: ({ getValue}) => {
          const tier = getValue();;
          return <TierBadge tier={tier} />;
        }
      },

      // Column 3: Users Count
      {
        header: 'Users',
        accessorKey: 'users_count',
        enableSorting: true,
        meta: {
          className: 'cell-center'
        },
        cell: ({ getValue }) => (
          <Typography variant="h6" color="text.secondary">
            {getValue() || 0}
          </Typography>
        )
      },

      // Column 4: Created Date
      {
        header: 'Created',
        accessorKey: 'created_at',
        enableSorting: true,
        cell: ({ getValue }) => (
          <Typography variant="body2" color="text.secondary">
            {formatDateTime(getValue())}
          </Typography>
                )
        },

      // Column 5: Actions
      {
        header: 'Actions',
        meta: {
          className: 'cell-center'
        },
        disableSortBy: true,
        enableSorting: false,
        cell: ({ row }) => {
          const role = row.original;
          const isAdminRole = Boolean(role?.is_admin);

          return (
            <Stack direction="row" alignItems="center" justifyContent="center" spacing={0}>
              {/* <Tooltip title="View">
                <IconButton
                  color="secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onView) onView(row.original);
                  }}
                >
                  <EyeOutlined />
                </IconButton>
              </Tooltip> */}
              <Tooltip title={isAdminRole ? 'Admin role cannot be edited' : 'Edit'}>
                <span>
                  <IconButton
                    color="secondary"
                    disabled={isAdminRole}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onEdit) onEdit(row.original);
                    }}
                  >
                    <EditOutlined />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Delete">
                <IconButton
                  color="secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onDelete) onDelete(row.original);
                  }}
                >
                  <DeleteOutlined />
                </IconButton>
              </Tooltip>
            </Stack>
          );
        }
      }
    ],
    [onView, onEdit, onDelete, theme]
  );

  // ==============================|| RENDER ||============================== //

  return (
    <ReusableTable
      data={data}
      columns={columns}
      loading={loading}
      error={error}
      swrKey={swrKey}
      modalToggler={modalToggler}
      totalCount={totalCount}
      currentPage={currentPage}
      onPaginationChange={onPaginationChange}
      onSearchChange={onSearchChange}
      sorting={sorting}
      onSortingChange={onSortingChange}
      initialPageSize={initialPageSize}
      addButtonLabel="Add Role"
      addButtonTooltip="Create new role"
      searchPlaceholder="Search roles..."
      exportFilename="roles-list.csv"
      emptyMessage="No roles found"
      emptyDescription="Start by creating your first role to manage user permissions"
      enableImport={false}
    />
  );
}

RoleTable.propTypes = {
  /**
   * Array of role data objects
   */
  data: PropTypes.array,
  
  /**
   * Loading state
   */
  loading: PropTypes.bool,
  
  /**
   * Error object from API call
   */
  error: PropTypes.object,
  
  /**
   * SWR cache key for revalidation
   */
  swrKey: PropTypes.any,
  
  /**
   * Function to open "Add Role" modal
   */
  modalToggler: PropTypes.func,
  
  /**
   * Total number of roles (for pagination)
   */
  totalCount: PropTypes.number,
  
  /**
   * Current page number (1-indexed)
   */
  currentPage: PropTypes.number,
  
  /**
   * Initial page size
   */
  initialPageSize: PropTypes.number,
  
  /**
   * Pagination change handler
   * @param {Object} params - { page: number, pageSize: number }
   */
  onPaginationChange: PropTypes.func,
  
  /**
   * Search change handler
   * @param {string} searchTerm - Search query
   */
  onSearchChange: PropTypes.func,
  
  /**
   * Current sorting state
   */
  sorting: PropTypes.array,
  
  /**
   * Sorting change handler
   */
  onSortingChange: PropTypes.func,
  
  /**
   * View role handler
   * @param {Object} role - Role object
   */
  onView: PropTypes.func,
  
  /**
   * Edit role handler
   * @param {Object} role - Role object
   */
  onEdit: PropTypes.func,
  
  /**
   * Delete role handler
   * @param {Object} role - Role object
   */
  onDelete: PropTypes.func
};

export default RoleTable;