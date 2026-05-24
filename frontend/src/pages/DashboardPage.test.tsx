import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { DashboardPage } from "./DashboardPage";

vi.mock("../lib/api/client", () => ({
  apiClient: {
    getAvailableYears: vi.fn(),
    getConfig: vi.fn(),
    listPaychecks: vi.fn(),
    listPensions: vi.fn(),
    listNonTaxableIncome: vi.fn(),
    projectYear: vi.fn(),
  },
}));

const currentYear = new Date().getFullYear();

const renderWithQueryClient = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  );
};

const defaultConfig = {
  filing_status: "single" as const,
  num_children: 0,
  use_standard_deduction: true,
  itemized_deduction_amount: "0.00",
  age_65_plus: false,
};

const defaultProjection = {
  year: currentYear,
  filing_status: "single" as const,
  w2_gross: "80000.00",
  w2_taxable: "75000.00",
  pension_taxable: "0.00",
  total_taxable_income: "61650.00",
  taxable_income: "61650.00",
  federal_tax_liability: "9000.00",
  fica_liability: "6120.00",
  total_tax_liability: "15120.00",
  estimated_withholding: "0.00",
  estimated_refund_or_owed: "0.00",
  // Backend returns rates already as percentages: "18.9" means 18.9%
  effective_rate: "18.9",
  marginal_rate: "22",
};

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getAvailableYears).mockResolvedValue({
      available_years: [currentYear],
      latest_year: currentYear,
      data_directory: "/data",
    });
    vi.mocked(apiClient.getConfig).mockResolvedValue(defaultConfig);
    vi.mocked(apiClient.listPaychecks).mockResolvedValue([]);
    vi.mocked(apiClient.listPensions).mockResolvedValue([]);
    vi.mocked(apiClient.listNonTaxableIncome).mockResolvedValue([]);
    vi.mocked(apiClient.projectYear).mockResolvedValue(defaultProjection);
  });

  it("renders YTD cashflow section", async () => {
    renderWithQueryClient();
    await screen.findByText(/Household Cashflow/);
    expect(screen.getByText(/Household Cashflow/)).toBeInTheDocument();
    expect(screen.getByText("Federal Withholding")).toBeInTheDocument();
    expect(screen.getByText("W-2 Gross")).toBeInTheDocument();
  });

  it("displays effective rate as a plain percentage (not multiplied by 100 again)", async () => {
    renderWithQueryClient();
    // Wait for prediction to load
    await screen.findByText(/Projected Total Tax Liability/);

    // The backend returns effective_rate = "18.9" meaning 18.9%
    // It must render as "18.9% effective", NOT "1890.0% effective"
    const caption = await screen.findByText(/effective/);
    expect(caption.textContent).toMatch(/^18\.9% effective/);
    expect(caption.textContent).not.toMatch(/18[89]\d+\.?\d*%/); // not 1890% or similar
  });

  it("displays marginal rate as a plain percentage (not multiplied by 100 again)", async () => {
    renderWithQueryClient();
    await screen.findByText(/Projected Total Tax Liability/);

    const caption = await screen.findByText(/marginal/);
    // backend returns "22" meaning 22%, must render "22% marginal"
    expect(caption.textContent).toMatch(/22% marginal/);
    expect(caption.textContent).not.toMatch(/2200% marginal/);
  });

  it("renders projection cards when data is available", async () => {
    renderWithQueryClient();
    await screen.findByText(/Projected Household Cashflow/);
    expect(screen.getByText(/Projected W-2 Gross/)).toBeInTheDocument();
    expect(screen.getByText(/Projected 1099-R Gross/)).toBeInTheDocument();
    expect(screen.getByText(/Projected Total Tax Liability/)).toBeInTheDocument();
  });

  it("does not render ConfigEditor on the dashboard", async () => {
    renderWithQueryClient();
    await screen.findByText(/Household Cashflow/);
    expect(screen.queryByText("Tax Settings")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Filing Status")).not.toBeInTheDocument();
  });
});
