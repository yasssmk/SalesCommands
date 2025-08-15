'use client';
import { useMemo, useState } from 'react';

// material-ui
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// third-party
import { PatternFormat } from 'react-number-format';

// project-import
import Avatar from 'components/@extended/Avatar';
import IconButton from 'components/@extended/IconButton';
import { IndeterminateCheckbox } from 'components/third-party/react-table';

import UserModal from 'sections/admin/users/UserModal';
import AlertUserDelete from 'sections/admin/users/AlertUserDelete';
import UserTable from 'sections/admin/users/UserTable';

import { useGetUsers } from 'api/admin/users';

// assets
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';

// ==============================|| USER LIST ||============================== //

export default function UserListPage() {
  const { usersLoading, users: lists } = useGetUsers();

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
        id: 'select',
        header: ({ table }) => (
          <IndeterminateCheckbox
            {...{
              checked: table.getIsAllRowsSelected(),
              indeterminate: table.getIsSomeRowsSelected(),
              onChange: table.getToggleAllRowsSelectedHandler()
            }}
          />
        ),
        cell: ({ row }) => (
          <IndeterminateCheckbox
            {...{
              checked: row.getIsSelected(),
              disabled: !row.getCanSelect(),
              indeterminate: row.getIsSomeSelected(),
              onChange: row.getToggleSelectedHandler()
            }}
          />
        )
      },
      {
        header: '#',
        accessorKey: 'id',
        meta: {
          className: 'cell-center'
        }
      },
      {
        header: 'User Info',
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
              <Typography variant="caption" color="text.secondary">
                {row.original.email}
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
              getValue() === 'Manager' ? 'warning' :
              getValue() === 'User' ? 'primary' : 'default'
            }
          />
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
        header: 'Actions',
        meta: {
          className: 'cell-center'
        },
        disableSortBy: true,
        cell: ({ row }) => {
          const collapseIcon = row.getCanExpand() && row.getIsExpanded() ? 
            <PlusOutlined style={{ transform: 'rotate(45deg)' }} /> : <EyeOutlined />;
          return (
            <Stack direction="row" alignItems="center" justifyContent="center" spacing={0}>
              <Tooltip title="View">
                <IconButton
                  color={row.getIsExpanded() ? 'error' : 'secondary'}
                  onClick={row.getToggleExpandedHandler()}
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
                    setUserDeleteId(row.original.id);
                    setOpen(true);
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
    [open]
  );


  return (
    <>
      <UserTable
        {...{
          data: lists || [],
          columns,
          modalToggler: () => {
            setUserModal(true);
            setSelectedUser(null);
          }
        }}
      />
      <AlertUserDelete 
        id={userDeleteId} 
        title={selectedUser?.first_name + ' ' + selectedUser?.last_name || 'User'} 
        open={open} 
        handleClose={handleClose} 
      />
      <UserModal open={userModal} modalToggler={setUserModal} user={selectedUser} />
    </>
  );
}