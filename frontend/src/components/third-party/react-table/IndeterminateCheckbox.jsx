// import PropTypes from 'prop-types';
// // material-ui
// import Checkbox from '@mui/material/Checkbox';

// // ==============================|| ROW SELECTION - CHECKBOX ||============================== //

// export default function IndeterminateCheckbox({ indeterminate, ...rest }) {
//   return <Checkbox {...rest} indeterminate={typeof indeterminate === 'boolean' && !rest.checked && indeterminate} />;
// }

// IndeterminateCheckbox.propTypes = { indeterminate: PropTypes.bool };

import PropTypes from 'prop-types';
import { memo } from 'react';

// material-ui
import Checkbox from '@mui/material/Checkbox';

// ==============================|| ROW SELECTION - CHECKBOX ||============================== //

function IndeterminateCheckbox({ indeterminate, checked, ...rest }) {
  return (
    <Checkbox
      {...rest}
      checked={checked}
      indeterminate={!!indeterminate && !checked}
    />
  );
}

IndeterminateCheckbox.propTypes = {
  indeterminate: PropTypes.bool,
  checked: PropTypes.bool,
  onChange: PropTypes.func,
  disabled: PropTypes.bool
};

export default memo(IndeterminateCheckbox);