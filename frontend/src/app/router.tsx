import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router";
import { AppShell } from "./AppShell";

const DashboardPage = lazy(() =>
  import("../pages/DashboardPage").then(({ DashboardPage }) => ({ default: DashboardPage })),
);
const IncomePage = lazy(() =>
  import("../pages/IncomePage").then(({ IncomePage }) => ({ default: IncomePage })),
);
const TaxesPage = lazy(() =>
  import("../pages/TaxesPage").then(({ TaxesPage }) => ({ default: TaxesPage })),
);
const W4Page = lazy(() => import("../pages/W4Page").then(({ W4Page }) => ({ default: W4Page })));
const ProjectionsPage = lazy(() =>
  import("../pages/ProjectionsPage").then(({ ProjectionsPage }) => ({ default: ProjectionsPage })),
);
const CsvImportPage = lazy(() =>
  import("../pages/CsvImportPage").then(({ CsvImportPage }) => ({ default: CsvImportPage })),
);
const SettingsPage = lazy(() =>
  import("../pages/SettingsPage").then(({ SettingsPage }) => ({ default: SettingsPage })),
);

const loading = <p role="status">Loading page…</p>;

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      {
        index: true,
        element: (
          <Suspense fallback={loading}>
            <DashboardPage />
          </Suspense>
        ),
      },
      {
        path: "income",
        element: (
          <Suspense fallback={loading}>
            <IncomePage />
          </Suspense>
        ),
      },
      {
        path: "taxes",
        element: (
          <Suspense fallback={loading}>
            <TaxesPage />
          </Suspense>
        ),
      },
      {
        path: "w4",
        element: (
          <Suspense fallback={loading}>
            <W4Page />
          </Suspense>
        ),
      },
      {
        path: "projections",
        element: (
          <Suspense fallback={loading}>
            <ProjectionsPage />
          </Suspense>
        ),
      },
      {
        path: "imports",
        element: (
          <Suspense fallback={loading}>
            <CsvImportPage />
          </Suspense>
        ),
      },
      {
        path: "settings",
        element: (
          <Suspense fallback={loading}>
            <SettingsPage />
          </Suspense>
        ),
      },
    ],
  },
]);
