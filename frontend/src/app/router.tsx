import { createBrowserRouter } from "react-router-dom";
import { AuthPage } from "../pages/AuthPage";
import { CsvImportPage } from "../pages/CsvImportPage";
import { DashboardPage } from "../pages/DashboardPage";
import { IncomePage } from "../pages/IncomePage";
import { ProjectionsPage } from "../pages/ProjectionsPage";
import { SettingsPage } from "../pages/SettingsPage";
import { TaxesPage } from "../pages/TaxesPage";
import { W4Page } from "../pages/W4Page";
import { AppShell } from "./AppShell";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "income", element: <IncomePage /> },
      { path: "taxes", element: <TaxesPage /> },
      { path: "w4", element: <W4Page /> },
      { path: "projections", element: <ProjectionsPage /> },
      { path: "imports", element: <CsvImportPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "auth", element: <AuthPage /> },
    ],
  },
]);
