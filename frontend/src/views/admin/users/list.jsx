'use client';
import { useMemo, useState, useCallback, useEffect } from 'react';

// material-ui
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Checkbox from '@mui/material/Checkbox';

// project-import
import Avatar from 'components/@extended/Avatar';
import IconButton from 'components/@extended/IconButton';
import { RowSelection } from 'components/third-party/react-table';

import UserModal from 'sections/admin/users/UserModal';
import AlertUserDelete from 'sections/admin/users/AlertUserDelete';
import UserTable from 'sections/admin/users/UserTable';
import SeatsSummary from 'sections/admin/users/SeatsSummary';

import { useGetUsers } from 'api/admin/users';
import { useAuth } from 'hooks/useAuth';
import { tenantKey } from 'api/_swr';
import useLocalStorage from 'hooks/useLocalStorage';

// formatting
import { formatDateTime } from 'config/formatters';

// assets
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import { useTheme } from '@mui/material/styles';
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';

//TEST
import TestErrorButton from 'components/TestErrorButton';

// ==============================|| USER LIST ||============================== //

export default function UserListPage() {
  const theme = useTheme();
  const { tenantId } = useAuth();

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage(
    `userTablePageSize`, 10
  );

  const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    return (!isNaN(parsed) && parsed > 0) ? parsed : 10;
  }, [pageSize]);

  const [search, setSearch] = useState('');

  const { usersLoading, users, usersCount, usersError } = useGetUsers({
    page,
    pageSize: validPageSize,
    search
  });

  const swrKey = useMemo(() => {
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('page_size', pageSize);
    if (search) params.append('search', search);

    const url = `/client/users/${params.toString() ? `?${params.toString()}` : ''}`;
    return tenantKey(url, tenantId);
  }, [page, pageSize, search, tenantId]);

  const [open, setOpen] = useState(false);
  const [userModal, setUserModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDeleteId, setUserDeleteId] = useState('');
  
  // ✅ State de sélection
  const [selectedRows, setSelectedRows] = useState(new Set());

  // ==============================|| HANDLERS ||============================== //

  // ✅ Handler pagination - appelé par UserTable
  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newPageSize }) => {
      // Gestion du changement de page
      setPage(newPage);
      
      // Gestion du changement de pageSize avec persistance
      const size = Number(newPageSize);
      if (!isNaN(size) && size > 0 && size !== validPageSize) {
        setPageSize(size); // Persiste automatiquement dans localStorage
      }
    },
    [setPageSize, validPageSize]
  );

  // ✅ Handler recherche - appelé par UserTable
  const handleSearchChange = useCallback((searchTerm) => {
    setSearch(searchTerm);
    setPage(1);  // Reset à page 1 quand on recherche
  }, []);

  const handleClose = useCallback(() => {
    setOpen((prev) => !prev);
  }, []);

  const handleOpenEditModal = useCallback((user) => {
    setSelectedUser(user);
    setUserModal(true);
  }, []);

  const handleOpenDeleteDialog = useCallback(
    (user) => {
      setSelectedUser(user);
      setUserDeleteId(user.id);
      handleClose();
    },
    [handleClose]
  );

  // ✅ HANDLERS DE SÉLECTION - VERSION DEBUG
  const handleSelectAll = useCallback((e) => {
    e.stopPropagation();
    if (e.target.checked && users) {
      setSelectedRows(new Set(users.map(user => user.id)));
    } else {
      setSelectedRows(new Set());
    }
  }, [users]);

  const handleSelectRow = useCallback((userId) => {
    setSelectedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(userId)) {
        newSet.delete(userId);
      } else {
        newSet.add(userId);
      }
      return newSet;
    });
  }, []);

  // Calculs
  const allSelected = users && users.length > 0 && selectedRows.size === users.length;
  const someSelected = selectedRows.size > 0 && selectedRows.size < (users?.length || 0);


  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(
    () => [
      {
        id: 'select',
        enableSorting: false,
        header: () => {
          return (
            <div onClick={(e) => { e.stopPropagation(); }}>
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected}
                onChange={handleSelectAll}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              />
            </div>
          );
        },
        cell: ({ row }) => {
          const isSelected = selectedRows.has(row.original.id);
          return (
            <div onClick={(e) => { e.stopPropagation(); }}>
              <Checkbox
                checked={isSelected}
                onChange={(e) => {
                  e.stopPropagation();
                  handleSelectRow(row.original.id);
                }}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              />
            </div>
          );
        }
      },
      {
        header: 'User Name',
        accessorKey: 'full_name',
        cell: ({ getValue }) => (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="subtitle1">
              {getValue() || 'No Name'}
            </Typography>
          </Stack>
        )
      },
      {
        header: 'Email',
        accessorKey: 'email',
        cell: ({ getValue }) => (
          <Typography variant="h6">
            {getValue()}
          </Typography>
        )
      },
      {
        header: 'Role',
        accessorKey: 'role_name',
        cell: ({ row }) => {
          const roleTier = row.original.role_tier;
          const roleName = row.original.role_name || 'No Role';
          
          let textColor = 'text.primary';
          if (roleTier === 'admin') {
            textColor = 'error.main';
          } else if (roleTier === 'manager') {
            textColor = 'warning.main';
          } else if (roleTier === 'individual') {
            textColor = 'info.main';
          }
          
          return (
            <Typography 
              variant="h6" 
              sx={{ color: textColor }}
            >
              {roleName}
            </Typography>


          );
        }
      },
      {
        header: 'SuperUser',
        accessorKey: 'is_superuser',
        meta: {
          className: 'cell-center'  // ✅ Utilise le style cell-center de TableCell override
        },
        cell: ({ row }) => (
          row.original.is_superuser ? (
            <CheckCircleFilled 
              style={{ 
                fontSize: '20px',
                color: theme.palette.secondary.main
              }} 
            />
          ) : null
        )
      },
      {
        header: 'Team',
        accessorKey: 'team',
        cell: ({ row }) => {
          const teamName = row.original.team?.name || 'No Team';
          const isNoTeam = !row.original.team;
          
          return (
            <Typography 
              variant="h6"
              color={isNoTeam ? 'text.secondary' : 'inherit'}
            >
              {teamName}
            </Typography>
          );
        }
      },
      {
        header: 'Status',
        accessorKey: 'is_active',
        cell: ({ getValue }) => (
          <Chip color={getValue() ? 'success' : 'error'} label={getValue() ? 'Active' : 'Inactive'} size="small" variant="light" />
        )
      },
      {
        header: 'Last connection',
        accessorKey: 'last_login',
        cell: ({ getValue }) => {
          const v = getValue();
          return <Typography variant="body2" color="text.secondary">{v ? formatDateTime(v) : 'Never'}</Typography>;
        }
      },
      {
        header: 'Actions',
        meta: {
          className: 'cell-center'
        },
        disableSortBy: true,
        cell: ({ row }) => {
          const collapseIcon =
            row.getCanExpand() && row.getIsExpanded() ? (
              <Tooltip title="Close">
                <EyeOutlined style={{ color: theme.palette.error.main, transform: 'rotate(90deg)' }} />
              </Tooltip>
            ) : (
              <Tooltip title="View">
                <EyeOutlined />
              </Tooltip>
            );

          return (
            <Stack direction="row" alignItems="center" justifyContent="center" spacing={0}>
              <Tooltip title="View">
                <IconButton
                  color="secondary.500"
                  onClick={(e) => {
                    e.stopPropagation();
                    row.toggleExpanded();
                  }}
                >
                  {collapseIcon}
                </IconButton>
              </Tooltip>
              <Tooltip title="Edit">
                <IconButton
                  color="secondary.500"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenEditModal(row.original);
                  }}
                >
                  <EditOutlined />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete">
                <IconButton
                  color="secondary.500"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenDeleteDialog(row.original);
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
    [theme, handleOpenEditModal, handleOpenDeleteDialog, allSelected, someSelected, handleSelectAll, selectedRows, handleSelectRow]
  );

  return (
    <>
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <SeatsSummary />
      </Grid>

      <UserTable
        data={users|| []}
        columns={columns}
        loading={usersLoading}
        error={usersError}
        swrKey={swrKey}
        selectedCount={selectedRows.size}
        selectedRows={selectedRows}
        totalCount={usersCount} 
        onPaginationChange={handlePaginationChange}      
        onSearchChange={handleSearchChange}              
        modalToggler={() => {
          setSelectedUser(null);
          setUserModal(true);
          
        }}
        initialPageSize={pageSize}  
      />

      <UserModal open={userModal} modalToggler={setUserModal} user={selectedUser} />

      <AlertUserDelete
        id={userDeleteId}
        title={selectedUser ? `${selectedUser.first_name} ${selectedUser.last_name}` : ''}
        open={open}
        handleClose={handleClose}
      />
      {/* Test Error Button (dev only) */}
      {process.env.NODE_ENV === 'development' && <TestErrorButton />}
    </>
  );
}