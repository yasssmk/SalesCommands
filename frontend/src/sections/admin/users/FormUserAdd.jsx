import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';

// project imports
import { openSnackbar } from 'api/snackbar';

// assets
import ToolOutlined from '@ant-design/icons/ToolOutlined';

// ==============================|| USER FORM PLACEHOLDER ||============================== //

export default function FormUserAdd({ user, closeModal }) {
  const handlePlaceholderAction = () => {
    openSnackbar({
      open: true,
      message: 'User form is under construction. Coming soon!',
      variant: 'alert',
      alert: {
        color: 'info'
      }
    });
  };

  return (
    <>
      <DialogTitle>{user ? 'Edit User' : 'New User'}</DialogTitle>
      <Divider />
      <DialogContent sx={{ p: 4 }}>
        <Stack spacing={3} alignItems="center" justifyContent="center" sx={{ minHeight: 300 }}>
          <ToolOutlined style={{ fontSize: '4rem', color: '#1976d2' }} />
          <Typography variant="h4" color="primary">
            En construction
          </Typography>
          <Typography variant="body1" color="text.secondary" textAlign="center">
            Le formulaire d'ajout/édition d'utilisateur est en cours de développement.
            <br />
            Cette fonctionnalité sera disponible prochainement.
          </Typography>
          <Button 
            variant="outlined" 
            color="primary" 
            onClick={handlePlaceholderAction}
            sx={{ mt: 2 }}
          >
            En savoir plus
          </Button>
        </Stack>
      </DialogContent>
      <Divider />
      <DialogActions sx={{ p: 2.5 }}>
        <Button color="primary" variant="contained" onClick={closeModal}>
          Fermer
        </Button>
      </DialogActions>
    </>
  );
}

FormUserAdd.propTypes = { 
  user: PropTypes.any, 
  closeModal: PropTypes.func 
};