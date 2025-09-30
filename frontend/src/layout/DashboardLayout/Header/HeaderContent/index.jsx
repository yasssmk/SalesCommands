import { useMemo } from 'react';

import useMediaQuery from '@mui/material/useMediaQuery';
import Box from '@mui/material/Box';

// project import
import Search from './Search';
import Profile from './Profile';
import FullScreen from './FullScreen';

import { MenuOrientation } from 'config';
import useConfig from 'hooks/useConfig';

// import DrawerHeader from 'layout/DashboardLayout/Drawer/DrawerHeader';

// ==============================|| HEADER - CONTENT ||============================== //

export default function HeaderContent() {
  const { menuOrientation } = useConfig();

  const downLG = useMediaQuery((theme) => theme.breakpoints.down('lg'));


return (
    <>
      {/* {menuOrientation === MenuOrientation.HORIZONTAL && !downLG && <DrawerHeader open={true} />} */}
      {!downLG && <Search />}

      {/* Spacer mobile: prend l'espace sans forcer une largeur pleine */}
      {downLG && <Box sx={{ flexGrow: 1, ml: 1 }} />}

      {!downLG && <FullScreen />}

      {/* Un seul Profile suffit (desktop + mobile) */}
      <Profile />
    </>
  );

}
