'use client';
import { useMemo, useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

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

import EmptyReactTable from 'views/tables/react-table/empty';
import AccountModal from 'sections/crm/accounts/AccountModal';
import AlertAccountDelete from 'sections/crm/accounts/AlertAccountDelete';
import AccountTable from 'sections/crm/accounts/AccountTable';

import { openSnackbar } from 'api/snackbar'

import { useGetAccounts } from 'api/(crm)/account'

// assets
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';

import ReactTable from 'views/tables/react-table/column-visibility'
import { set } from 'lodash';
import { use } from 'react';


// ==============================|| CUSTOMER LIST ||============================== //

export default function AccountListPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [accountModal, setAccountModal] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [accountDeleteName, setAccountDeleteName] = useState('');
  const [accountDeleteId, setAccountDeleteId] = useState('');
  const [filters, setFilters] = useState({});

  

  // Fetch accounts with react-query
  const { data: accounts, isLoading, isError, error} = useQuery({
    queryKey: ['accounts', filters],
    queryFn: () => useGetAccounts(filters),
  });

  useEffect(() => {
    if (isError) {
      openSnackbar({
        open: true,
        message: 'Error try again later',
        anchorOrigin: { vertical: 'top', horizontal: 'right' },
        variant: 'alert',
        alert: {
          color: 'error'
        }
      });
    }
  })

  
  const safeAccounts = accounts ?? [];

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
      // {
      //   header: '#',
      //   accessorKey: 'id',
      //   meta: {
      //     className: 'cell-center'
      //   }
      // },
      {
        header: 'Company Name',
        accessorKey: 'company_name',
        cell: ({ row }) => (
              <Typography variant="subtitle1">{row.original.company_name}</Typography>
        )
      },
      {
        header: 'Industry',
        accessorKey: 'industry',
        cell: ({ getValue }) => (
          getValue() ? `${getValue().toLocaleString()}` : 'N/A'
        ),
        meta: {
          className: 'cell-right'
        }
      },
      {
        header: 'Type',
        accessorKey: 'type',
        cell: ({ getValue }) => (
          <Chip 
            label={getValue() || 'N/A'} 
            size="small" 
            variant="light"
            color={
              getValue() === 'CLIENT' ? 'success' :
              getValue() === 'PROSPECT' ? 'warning' :
              getValue() === 'PARTNER' ? 'info' :
              getValue() === 'VENDOR' ? 'secondary' : 'default'
            }
          />
        )
      },
      {
        header: 'Classification',
        accessorKey: 'classification',
        cell: ({ getValue }) => (
          <Chip 
            label={getValue() || 'N/A'} 
            size="small" 
            variant="light"
            color="primary"
          />
        )
      },
      {
        header: 'Phone',
        accessorKey: 'phone_number',
        cell: ({ getValue }) => (
          getValue() ? `${getValue().toLocaleString()}` : 'N/A'
        )
      },
      {
        header: 'City',
        accessorKey: 'city',
        cell: ({ row }) => (
          `${row.original.city}`
        )
      },
      {
        header: 'Country',
        accessorKey: 'country',
        cell: ({ row }) => (
          `${row.original.country}`
        )
      },
      {
        header: 'Potential',
        accessorKey: 'potential',
        cell: ({ getValue }) => (
          getValue() ? `$${getValue().toLocaleString()}` : 'N/A'
        ),
        meta: {
          className: 'cell-right'
        }
      },
      {
        header: 'Employees',
        accessorKey: 'number_of_employees',
        cell: ({ getValue }) => (
          getValue() ? `${getValue().toLocaleString()}` : 'N/A'
        ),
        meta: {
          className: 'cell-right'
        }
      },
      {
        header: 'Account Owner',
        accessorKey: 'account_owner',
        cell: ({ row }) => (
          `N/A`
        ),
        meta: {
          className: 'cell-right'
        }
      },
      {
        header: 'Actions',
        meta: {
          className: 'cell-center'
        },
        cell: ({ row }) => {
          const collapseIcon = row.getCanExpand() ? 
            <PlusOutlined style={{ transform: row.getIsExpanded() ? 'rotate(45deg)' : 'none' }} /> : 
            <EyeOutlined />;
            
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
                    setSelectedAccount(row.original);
                    setAccountModal(true);
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
                    setOpen(true);
                    setAccountDeleteName(row.original.company_name);
                    setAccountDeleteId(row.original.id);
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
    []
  );

  if (isLoading) return <EmptyReactTable />;

  return (
    <>
      <AccountTable
        data={safeAccounts}
        columns={columns}
        modalToggler={() => {
          setAccountModal(true);
          setSelectedAccount(null);
        }}
        onFilterChange={setFilters}
      />
      <AlertAccountDelete 
        id={accountDeleteId}
        account_name={accountDeleteName}
        open={open}
        handleClose={handleClose}
        onConfirm={() => queryClient.invalidateQueries(['accounts'])}
      />
      <AccountModal 
        open={accountModal}
        modalToggler={setAccountModal}
        account={selectedAccount}
        onSuccess={() => queryClient.invalidateQueries(['accounts'])}
      />
    </>
  );
}