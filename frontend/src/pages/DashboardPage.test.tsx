import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { DashboardPage } from "./DashboardPage";

vi.mock("../lib/api/client", () => ({
  apiClient: {
    getAvailableYears: vi.fn(),
    listPaychecks: vi.fn(),
    listPensions: vi.fn(),
    listNonTaxableIncome: vi.fn(),
    getDashboardProjection: vi.fn(),
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

const defaultDashboardProjection = {
  year: currentYear,
  is_current_year: true,
  as_of_date: "2025-05-31",
  ytd: {
    w2_gross: "40000.00",
    w2_pretax: "5000.00",
    w2_federal_withheld: "4800.00",
    pension_gross: "0.00",
    pension_pretax: "0.00",
    pension_federal_withheld: "0.00",
    va_income: "0.00",
    paycheck_count: 4,
    pension_count: 0,
    non_taxable_count: 0,
  },
  projected: {
    w2_gross: "80000.00",
    w2_pretax: "10000.00",
    pension_gross: "0.00",
    pension_pretax: "0.00",
    va_income: "0.00",
    total_tax_liability: "15120.00",
    federal_income_tax: "9000.00",
    fica_total: "6120.00",
    effective_rate: "18.9",
    marginal_rate: "22",
    total_withheld: "9600.00",
    refund_or_owed: "-5520.00",
  },
  remaining_periods: { w2: 8, pension: 7, non_taxable: 7 },
};

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getAvailableYears).mockResolvedValue({
      available_years: [currentYear],
      latest_year: currentYear,
      data_directory: "/data",
    });
    vi.mocked(apiClient.listPaychecks).mockResolvedValue([]);
    vi.mocked(apiClient.listPensions).mockResolvedValue([]);
    vi.mocked(apiClient.listNonTaxableIncome).mockResolvedValue([]);
    vi.mocked(apiClient.getDashboardProjection).mockResolvedValue(defaultDashboardProjection);
  });

  it("renders YTD cashflow section", async () => {
    renderWithQueryClient();
    const cashflowCards = await screen.findAllByText(/Household Cashflow/);
    expect(cashflowCards.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Federal Withholding")).toBeInTheDocument();
    expect(screen.getByText("W-2 Gross")).toBeInTheDocument();
  });

  it("displays effective rate as a plain percentage (not multiplied by 100 again)", async () => {
    renderWithQueryClient();
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

  it("shows projected note with as_of_date for current year", async () => {
    renderWithQueryClient();
    await screen.findByText(/Projected Household Cashflow/);
    expect(screen.getByText(/Projected from YTD \+ remaining pay periods/)).toBeInTheDocument();
  });

  it("does not render ConfigEditor on the dashboard", async () => {
    renderWithQueryClient();
    await screen.findAllByText(/Household Cashflow/);
    expect(screen.queryByText("Tax Settings")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Filing Status")).not.toBeInTheDocument();
  });
});
