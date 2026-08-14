import useMediaQuery from "@mui/material/useMediaQuery";

// project import
// import NavUser from './NavUser';
// import NavCard from './NavCard';
import Navigation from "./Navigation";
import SimpleBar from "components/third-party/SimpleBar";
import { useMenuState } from "hooks/useMenuState";
import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import List from "@mui/material/List";
import Typography from "@mui/material/Typography";

// ==============================|| DRAWER CONTENT ||============================== //

export default function DrawerContent() {
  const { menuMaster } = useMenuState();
  const drawerOpen = menuMaster.isDashboardDrawerOpened;

  const downLG = useMediaQuery((theme) => theme.breakpoints.down("lg"));

  return (
    <>
      <SimpleBar
        sx={{
          "& .simplebar-content": {
            display: "flex",
            flexDirection: "column",
          },
        }}
      >
        <Navigation />

        {/* Placeholder pour NavCard future */}
        {drawerOpen && !downLG && (
          <Box sx={{ p: 2, borderTop: "1px solid", borderColor: "divider" }}>
            <Typography variant="caption" color="text.disabled">
              NavCard placeholder qwerty
            </Typography>
          </Box>
        )}
      </SimpleBar>

      {/* Placeholder pour NavUser future */}
      <Box
        sx={{
          p: 2,
          borderTop: "1px solid",
          borderColor: "divider",
          mt: "auto",
        }}
      >
        <Typography variant="caption" color="text.disabled">
          NavUser placeholder
        </Typography>
      </Box>
    </>
  );

  // return (
  //   <>
  //     <SimpleBar
  //       sx={{
  //         '& .simplebar-content': {
  //           display: 'flex',
  //           flexDirection: 'column'
  //         }
  //       }}
  //     >
  //       <Navigation />
  //       {drawerOpen && !downLG && <NavCard />}
  //     </SimpleBar>
  //     <NavUser />
  //   </>
  // );
}
