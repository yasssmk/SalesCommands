import PropTypes from 'prop-types';

import ButtonBase from '@mui/material/ButtonBase';
import Link from '@mui/material/Link';

// project import
import LogoMain from './LogoMain';
import LogoIcon from './LogoIcon';

import { APP_DEFAULT_PATH } from 'config';

export default function LogoSection({ reverse, isIcon, sx, to }) {
  return (
    <Link href={!to ? APP_DEFAULT_PATH : to} >
      <ButtonBase disableRipple sx={sx}>
        {isIcon ? <LogoIcon /> : <LogoMain reverse={reverse} />}
      </ButtonBase>
    </Link>
  );
}

LogoSection.propTypes = { reverse: PropTypes.bool, isIcon: PropTypes.bool, sx: PropTypes.any, to: PropTypes.string };
