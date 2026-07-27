// frontend/src/sections/objectives/ObjectiveModal.jsx
//
// Create / edit modal for an objective — mirrors TerritoryModal (a Dialog that
// mounts the Formik form). `objective` set => edit; absent => create.

import PropTypes from 'prop-types';
import Dialog from '@mui/material/Dialog';

import ObjectiveForm from './ObjectiveForm';

export default function ObjectiveModal({ open, closeModal, objective }) {
  return (
    <Dialog open={open} onClose={closeModal} fullWidth maxWidth="sm">
      {open && <ObjectiveForm objective={objective} closeModal={closeModal} />}
    </Dialog>
  );
}

ObjectiveModal.propTypes = {
  open: PropTypes.bool.isRequired,
  closeModal: PropTypes.func.isRequired,
  objective: PropTypes.object,
};
