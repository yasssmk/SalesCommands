'use client';
import { useMemo, useState } from 'react';

// material-ui
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';

// third-party
import { PatternFormat } from 'react-number-format';

// project-import
import Avatar from 'components/@extended/Avatar';
import IconButton from 'components/@extended/IconButton';
import { IndeterminateCheckbox } from 'components/third-party/react-table';

import UserModal from 'sections/admin/users/UserModal';
import AlertUserDelete from 'sections/admin/users/AlertUserDelete';
import UserTable from 'sections/admin/users/UserTable';
import UserSeatsCard from 'sections/admin/users/UserSeatsCard';
import SeatsSummary from 'sections/admin/users/SeatsSummary';

import { useGetUsers } from 'api/admin/users';
import { useAuth } from 'hooks/useAuth';
import { tenantKey } from 'api/_swr';

// formatting (standardized across the app)
import { formatDateTime } from 'config/formatters'; 

// assets
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import { useTheme } from '@mui/material/styles';
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';

//TEST
import TestErrorButton from 'components/TestErrorButton';

// ==============================|| USER LIST ||============================== //

export default function UserListPage() {
  const theme = useTheme();
  const { tenantId } = useAuth();
  
  // ✅ STEP 1: Get error from hook
  const { usersLoading, users: lists, usersError } = useGetUsers();

  
  // ✅ STEP 2: Create SWR key for mutate (retry functionality)
  const swrKey = tenantKey('/client/users/', tenantId);

  const [open, setOpen] = useState(false);

  const [userModal, setUserModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDeleteId, setUserDeleteId] = useState('');

  const handleClose = () => {
    setOpen(!open);
  };

  const columns = useMemo(
    () => [
      {
        header: 'User Name',
        accessorKey: 'first_name',
        cell: ({ row, getValue }) => (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Avatar 
              alt="User Avatar" 
              size="sm" 
              src={`/assets/images/users/avatar-${!row.original.avatar ? 1 : row.original.avatar}.png`}
            >
              {row.original.first_name?.charAt(0)}{row.original.last_name?.charAt(0)}
            </Avatar>
            <Stack spacing={0}>
              <Typography variant="subtitle1">
                {`${row.original.first_name || ''} ${row.original.last_name || ''}`.trim() || 'No Name'}
              </Typography>
            </Stack>
          </Stack>
        )
      },
      {
        header: 'Email',
        accessorKey: 'email',
        cell: ({ getValue }) => getValue()
      },
      {
        header: 'Role',
        accessorKey: 'role_name',
        cell: ({ getValue }) => (
          <Chip 
            label={getValue() || 'No Role'} 
            size="small" 
            variant="light"
            color={
              getValue() === 'Admin' ? 'error' :
              getValue() === 'Team Manager' ? 'warning' :
              getValue() === 'Direction' ? 'primary' : 
              getValue() === 'Account Executive' ? 'info' : 
              getValue() === 'Business Developer' ? 'success' : 'default'
            }
          />
        )
      },
      {
        header: 'SuperUser',
        accessorKey: 'is_superuser',
        cell: ({ row }) => (
          row.original.is_superuser ? (
            <CheckCircleFilled 
              style={{ 
                fontSize: '20px',
                color: theme.palette.error.light
              }} 
            />
          ) : null
        )
      },
      {
        header: 'Organization',
        accessorKey: 'organization',
        cell: ({ row }) => (
          <Typography variant="body2">
            {row.original.organization?.name || 'No Organization'}
          </Typography>
        )
      },
      {
        header: 'Team',
        accessorKey: 'team',
        cell: ({ row }) => (
          <Typography variant="body2">
            {row.original.team?.name || 'No Team'}
          </Typography>
        )
      },
      {
        header: 'Status',
        accessorKey: 'is_active',
        cell: ({ getValue }) => (
          <Chip
            color={getValue() ? 'success' : 'error'}
            label={getValue() ? 'Active' : 'Inactive'}
            size="small"
            variant="light"
          />
        )
      },
      {
        header: 'Last connection',
        accessorKey: 'last_login',
        cell: ({ getValue }) => {
          const v = getValue();
          return <Typography variant="body2">{v ? formatDateTime(v) : 'Never'}</Typography>;
        }
      },
      {
        header: 'Actions',
        meta: {
          className: 'cell-center'
        },
        disableSortBy: true,
        cell: ({ row }) => {
          const collapseIcon = row.getCanExpand() && row.getIsExpanded() ? (
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
                  color="secondary"
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
                  color="primary"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedUser(row.original);
                    setUserModal(true);
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
                    setSelectedUser(row.original);
                    handleClose();
                    setUserDeleteId(row.original.id);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme]
  );

  return (
  <>
    <Grid container spacing={2} sx={{ mb: 2 }}>
      <SeatsSummary />
    </Grid>

    <UserTable
      data={lists || []}
      columns={columns}
      loading={usersLoading}
      error={usersError}        // ✅ STEP 3: Pass error to UserTable
      swrKey={swrKey}            // ✅ STEP 4: Pass SWR key for retry
      modalToggler={() => {
        setSelectedUser(null);
        setUserModal(true);
      }}
    />

    {/* Add/Edit User Modal */}
    <UserModal 
      open={userModal} 
      modalToggler={setUserModal} 
      user={selectedUser} 
    />

    {/* Delete Confirmation */}
    <AlertUserDelete 
      id={userDeleteId} 
      title={
        selectedUser
          ? `${selectedUser.first_name || ''} ${selectedUser.last_name || ''}`.trim() + ` (${selectedUser.email})`
          : 'User'
      }
      open={open} 
      handleClose={handleClose} 
    />

    {/* Test Error Button (dev only) */}
    {process.env.NODE_ENV === 'development' && <TestErrorButton />}
  </>
);
}