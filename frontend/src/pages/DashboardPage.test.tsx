import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
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
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <DashboardPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
};

const defaultDashboardProjection = {
  year: currentYear,
  is_current_year: true,
  as_of_date: "2025-05-31",
  ytd: {
    w2_gross: "40000.00",
    w2_pretax_deductions: "5000.00",
    federal_withheld: "4800.00",
    pension_gross: "0.00",
    pension_pretax_deductions: "0.00",
    va_income: "0.00",
    paycheck_count: 4,
    pension_count: 0,
    non_taxable_count: 0,
  },
  projected: {
    w2_gross: "80000.00",
    w2_taxable: "70000.00",
    pension_gross: "0.00",
    pension_taxable: "0.00",
    total_taxable_income: "70000.00",
    taxable_income: "37800.00",
    deduction_type: "Standard Deduction",
    deduction_amount: "32200.00",
    va_income: "0.00",
    total_tax_liability: "15120.00",
    federal_tax_liability: "9000.00",
    fica_liability: "6120.00",
    effective_rate: "18.9",
    marginal_rate: "22",
    estimated_withholding: "9600.00",
    estimated_refund_or_owed: "-5520.00",
  },
  remaining_periods: { w2: 8, pension: 7, non_taxable: 7 },
};

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

describe("DashboardPage", () => {
  it("renders YTD cashflow section", async () => {
    renderWithQueryClient();
    const cashflowCards = await screen.findAllByText(/Household Cashflow/);
    expect(cashflowCards.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Federal Withholding")).toBeInTheDocument();
    expect(screen.getByText("W-2 Gross")).toBeInTheDocument();
  });

  it("displays effective rate as a plain percentage (not multiplied by 100 again)", async () => {
    renderWithQueryClient();
    await screen.findByText(/Projected amount due/);

    // The backend returns effective_rate = "18.9" meaning 18.9%
    // It must render as "18.9% effective", NOT "1890.0% effective"
    const caption = await screen.findByText(/effective federal rate/);
    expect(caption.textContent).toMatch(/^18\.9% effective/);
    expect(caption.textContent).not.toMatch(/18[89]\d+\.?\d*%/); // not 1890% or similar
  });

  it("displays marginal rate as a plain percentage (not multiplied by 100 again)", async () => {
    renderWithQueryClient();
    await screen.findByText(/Projected amount due/);

    const caption = await screen.findByText(/marginal rate/);
    // backend returns "22" meaning 22%, must render "22% marginal"
    expect(caption.textContent).toMatch(/22% marginal rate/);
    expect(caption.textContent).not.toMatch(/2200% marginal/);
  });

  it("renders the full-year projection when data is available", async () => {
    renderWithQueryClient();
    await screen.findByText("Full-year projection");
    expect(screen.getByText("Projected household income")).toBeInTheDocument();
    expect(screen.getByText("Federal income tax liability")).toBeInTheDocument();
    expect(screen.getByText("Projected net after tax")).toBeInTheDocument();
  });

  it("shows projected note with as_of_date for current year", async () => {
    renderWithQueryClient();
    await screen.findByText("Full-year projection");
    expect(screen.getByText(/Based on records through 2025-05-31/)).toBeInTheDocument();
  });

  it("does not render ConfigEditor on the dashboard", async () => {
    renderWithQueryClient();
    await screen.findAllByText(/Household Cashflow/);
    expect(screen.queryByText("Tax Settings")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Filing Status")).not.toBeInTheDocument();
  });
});

it.each([
  ["1300", "Projected refund", "$1,300.00"],
  ["-700", "Projected amount due", "$700.00"],
  ["0", "Projected balance", "$0.00"],
])("renders the backend balance %s", async (balance, label, amount) => {
  vi.mocked(apiClient.getDashboardProjection).mockResolvedValue({
    ...defaultDashboardProjection,
    projected: { ...defaultDashboardProjection.projected, estimated_refund_or_owed: balance },
  });
  renderWithQueryClient();
  await screen.findByRole("heading", { name: label });
  expect(within(screen.getByRole("region", { name: label })).getByText(amount)).toBeInTheDocument();
});

it("does not turn an incomplete response into a zero balance", async () => {
  const incomplete = structuredClone(defaultDashboardProjection);
  // Simulate a server contract regression despite the compile-time type.
  Reflect.deleteProperty(incomplete.projected, "estimated_refund_or_owed");
  vi.mocked(apiClient.getDashboardProjection).mockResolvedValue(incomplete);
  renderWithQueryClient();
  await screen.findByText("Projection unavailable");
  expect(screen.queryByRole("heading", { name: "Projected balance" })).not.toBeInTheDocument();
});

it("shows loading and request failures without a financial balance", async () => {
  vi.mocked(apiClient.getDashboardProjection).mockRejectedValue(new Error("Calculation failed"));
  renderWithQueryClient();
  await screen.findByText("Projection unavailable");
  expect(screen.getByText(/Projection unavailable: Calculation failed/)).toBeInTheDocument();
});

it("shows a loading state while the projection is pending", async () => {
  vi.mocked(apiClient.getDashboardProjection).mockReturnValue(new Promise(() => {}));
  renderWithQueryClient();
  await screen.findByText("Calculating…");
  expect(screen.queryByRole("heading", { name: "Projected balance" })).not.toBeInTheDocument();
});

it("prefers the current year over available future tax tables", async () => {
  vi.mocked(apiClient.getAvailableYears).mockResolvedValue({
    available_years: [currentYear, currentYear + 1],
    latest_year: currentYear + 1,
    data_directory: "/data",
  });
  renderWithQueryClient();
  await screen.findByText("Projected amount due");
  expect(apiClient.getDashboardProjection).toHaveBeenCalledWith(currentYear);
  expect(apiClient.getDashboardProjection).not.toHaveBeenCalledWith(currentYear + 1);
});
