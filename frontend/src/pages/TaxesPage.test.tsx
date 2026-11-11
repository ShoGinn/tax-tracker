import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { TaxesPage } from "./TaxesPage";

vi.mock("../lib/api/client", () => ({
  apiClient: {
    getConfig: vi.fn(),
    calculateTaxes: vi.fn(),
    getAvailableYears: vi.fn(),
    calculateFromDb: vi.fn(),
  },
}));

describe("TaxesPage", () => {
  it("loads the saved profile into the direct calculator", async () => {
    vi.mocked(apiClient.getConfig).mockResolvedValue({
      filing_status: "single",
      num_children: 1,
      use_standard_deduction: true,
      itemized_deduction_amount: "0",
      age_65_plus: true,
      w2_pay_frequency: "monthly",
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <TaxesPage />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Direct Tax Calculator" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Age 65+")).toBeChecked());
  });

  it("loads and submits the saved profile in database reconciliation", async () => {
    vi.mocked(apiClient.getConfig).mockResolvedValue({
      filing_status: "head_of_household",
      num_children: 2,
      use_standard_deduction: false,
      itemized_deduction_amount: "24500",
      age_65_plus: true,
      w2_pay_frequency: "biweekly",
    });
    vi.mocked(apiClient.getAvailableYears).mockResolvedValue({
      available_years: [2026],
      latest_year: 2026,
      data_directory: "/tmp/tax-data",
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <TaxesPage />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Reconciliation from DB" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Filing status")).toHaveValue("head_of_household");
      expect(screen.getByLabelText("Qualifying children")).toHaveValue(2);
      expect(screen.getByLabelText("Age 65+")).toBeChecked();
      expect(screen.getByLabelText("Use standard deduction")).not.toBeChecked();
      expect(screen.getByLabelText("Itemized deduction amount")).toHaveValue(24500);
    });

    fireEvent.click(screen.getByRole("button", { name: "Run reconciliation" }));
    await waitFor(() =>
      expect(apiClient.calculateFromDb).toHaveBeenCalledWith(
        expect.any(Number),
        expect.objectContaining({
          filing_status: "head_of_household",
          num_children: 2,
          age_65_plus: true,
          use_standard_deduction: false,
          itemized_deduction_amount: 24500,
        }),
      ),
    );
  });
});

it("renders actual backend bracket fields, percentage units, and only the FICA total", async () => {
  vi.mocked(apiClient.getConfig).mockResolvedValue({
    filing_status: "single",
    num_children: 0,
    age_65_plus: false,
    use_standard_deduction: true,
    itemized_deduction_amount: "0",
    w2_pay_frequency: "monthly",
  });
  vi.mocked(apiClient.calculateTaxes).mockResolvedValue({
    gross_income: "60000",
    retirement_pretax_deductions: "0",
    adjusted_gross_income: "60000",
    deduction_amount: "16100",
    deduction_type: "Standard Deduction",
    taxable_income: "43900",
    federal_tax_owed: "5020",
    child_tax_credits: "0",
    total_tax_liability: "5020",
    effective_tax_rate: "8.3666666667",
    marginal_tax_rate: "12",
    breakdown_by_bracket: [
      { bracket_min: 0, bracket_max: 12400, rate: 0.1, taxable_amount: 12400, tax_amount: 1240 },
      {
        bracket_min: 12400,
        bracket_max: 50400,
        rate: 0.12,
        taxable_amount: 31500,
        tax_amount: 3780,
      },
    ],
    fica_taxes: {
      social_security_tax: "3720",
      medicare_tax: "870",
      additional_medicare_tax: "0",
      total_fica: "4590",
      ss_wage_base_limit: "184500",
      ss_taxable_wages: "60000",
    },
    total_household_income: "60000",
    notes: [],
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TaxesPage />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByLabelText("W-2 gross wages"), { target: { value: "60000" } });
  fireEvent.click(screen.getByRole("button", { name: "Calculate taxes" }));
  await screen.findByText("8.37%");
  expect(screen.getByText("12.0%")).toBeInTheDocument();
  expect(screen.getByText("$4,590.00")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show bracket breakdown" }));
  expect(screen.getByText("$31,500.00")).toBeInTheDocument();
  expect(screen.getByText("$3,780.00")).toBeInTheDocument();
  expect(screen.getByText("$0.00 – $12,400.00")).toBeInTheDocument();
  expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
});

it("rejects missing tax amounts instead of displaying a false zero", async () => {
  vi.mocked(apiClient.calculateTaxes).mockResolvedValue(
    {} as Awaited<ReturnType<typeof apiClient.calculateTaxes>>,
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TaxesPage />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByLabelText("W-2 gross wages"), { target: { value: "60000" } });
  fireEvent.click(screen.getByRole("button", { name: "Calculate taxes" }));
  await screen.findByText("Tax result unavailable: incomplete calculation response.");
  expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
});
