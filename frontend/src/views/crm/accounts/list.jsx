'use client';
import { useMemo, useState } from 'react';
import axios from 'axios';
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
import AlertCustomerDelete from 'sections/apps/customer/AlertCustomerDelete';
import AccountTable from 'sections/crm/accounts/AccountTable';

import { useGetCustomer } from 'api/customer';

// assets
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';


// ==============================|| API CALL||============================== //

const API_URL = 'http://localhost:8000/app/accounts';

const accountService = {
  getAccounts: async (filters = {}) => {
    const params = new URLSearchParams(filters);
    const response = await axios.get(`${API_URL}/accounts/?${params}`);
    return response.data;
  },
  
  deleteAccount: async (id) => {
    const response = await axios.delete(`${API_URL}/accounts/${id}/`);
    return response.data;
  }
};



// ==============================|| CUSTOMER LIST ||============================== //

export default function AccountListPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [accountModal, setAccountModal] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [accountDeleteId, setAccountDeleteId] = useState('');
  const [filters, setFilters] = useState({});

  // Fetch accounts with react-query
  const { data: accounts, isLoading } = useQuery({
    queryKey: ['accounts', filters],
    queryFn: () => accountService.getAccounts(filters)
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: accountService.deleteAccount,
    onSuccess: () => {
      queryClient.invalidateQueries(['accounts']);
      setOpen(false);
    }
  });

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
        header: 'Company Info',
        accessorKey: 'company_name',
        cell: ({ row }) => (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Avatar alt={row.original.company_name} size="sm" />
            <Stack spacing={0}>
              <Typography variant="subtitle1">{row.original.company_name}</Typography>
              <Typography color="text.secondary">{row.original.industry || 'N/A'}</Typography>
            </Stack>
          </Stack>
        )
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
        header: 'Location',
        accessorKey: 'city',
        cell: ({ row }) => (
          `${row.original.city}, ${row.original.country}`
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
        data={accounts}
        columns={columns}
        modalToggler={() => {
          setAccountModal(true);
          setSelectedAccount(null);
        }}
        onFilterChange={setFilters}
      />
      <AlertCustomerDelete 
        id={accountDeleteId}
        title={accountDeleteId}
        open={open}
        handleClose={handleClose}
        onConfirm={() => deleteMutation.mutate(accountDeleteId)}
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