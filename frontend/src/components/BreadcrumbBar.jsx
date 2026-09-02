// frontend/src/components/BreadcrumbBar.jsx
//
// UX Activity L0 — the single layout breadcrumb bar.
//
// Reads the contextual trail from useBreadcrumb (BreadcrumbContext) and renders
// it. ALWAYS rendered (even with an empty trail) at a CONSTANT height
// (theme.aphoriQ.breadcrumb.minHeight) so it reserves the same vertical space on
// every page → the stable anchor the workspace drawer coque aligns under (L2).
//
// Each segment { label, href? }: an href that is not the last segment renders as
// a client-side link (router.push); the last segment is the current page (plain
// text). Fully themed via aphoriQ + iconSizes — no hardcoded hex/px.
//
// This is the SINGLE breadcrumb of the app (L1): the legacy menu-derived
// @extended/Breadcrumbs was removed from the layout and each page declares its
// trail via useBreadcrumb.

"use client";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Breadcrumbs from "@mui/material/Breadcrumbs";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";

// next
import { useRouter } from "next/navigation";

// icons
import RightOutlined from "@ant-design/icons/RightOutlined";

// project imports
import { useBreadcrumb } from "contexts/BreadcrumbContext";

// ==============================|| BREADCRUMB BAR ||============================== //

export default function BreadcrumbBar() {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const router = useRouter();
  const { crumbs } = useBreadcrumb();

  const items = Array.isArray(crumbs) ? crumbs : [];

  return (
    <Box
      data-testid="breadcrumb-bar"
      aria-label="breadcrumb"
      sx={{
        minHeight: aq.breadcrumb.minHeight,
        display: "flex",
        alignItems: "center",
        mb: 2,
      }}
    >
      {items.length > 0 && (
        <Breadcrumbs
          aria-label="fil"
          separator={<RightOutlined style={{ fontSize: theme.iconSizes.xs, color: aq.text.subtle }} />}
        >
          {items.map((item, index) => {
            const isLast = index === items.length - 1;

            if (item.href && !isLast) {
              return (
                <Link
                  key={index}
                  href={item.href}
                  onClick={(e) => {
                    e.preventDefault();
                    router.push(item.href);
                  }}
                  underline="hover"
                  variant="body2"
                  sx={{ color: aq.text.muted, cursor: "pointer" }}
                >
                  {item.label}
                </Link>
              );
            }

            return (
              <Typography
                key={index}
                variant="body2"
                sx={{ color: isLast ? "text.primary" : aq.text.muted, fontWeight: isLast ? 500 : 400 }}
              >
                {item.label}
              </Typography>
            );
          })}
        </Breadcrumbs>
      )}
    </Box>
  );
}
