import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { W4Page } from "./W4Page";

vi.mock("../lib/api/client", () => ({
  apiClient: {
    optimizeW4: vi.fn(),
    optimizeMidyearW4: vi.fn(),
    suggestMidyearPeriods: vi.fn(),
    calculateWithholding: vi.fn(),
    listEmployers: vi.fn(),
    getConfig: vi.fn(),
  },
}));

const currentYear = new Date().getFullYear();

const renderWithQueryClient = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <W4Page />
    </QueryClientProvider>,
  );
};

const midYearResponse = {
  year: currentYear,
  filing_status: "single",
  total_w2_income: "40000.00",
  total_pension_income: "0.00",
  total_va_income: "0.00",
  total_taxable_income: "40000.00",
  estimated_tax_liability: "4500.00",
  target_refund: "0.00",
  target_total_withholding: "4500.00",
  current_total_withholding: "2000.00",
  current_refund_or_owed: "-2500.00",
  adjustment_needed: "2500.00",
  w4_recommendations: [
    {
      employer_name: "Test Corp",
      filing_status: "single",
      step2_checkbox: false,
      step2_note: "",
      step3_amount: "0.00",
      step3_explanation: "",
      step4a_other_income: "0.00",
      step4a_explanation: "",
      step4b_deductions: "0.00",
      step4b_explanation: "",
      step4c_extra_withholding: "96.15",
      step4c_explanation: "Add extra withholding per check",
      expected_annual_withholding: "4500.00",
      expected_paychecks_per_year: 26,
    },
  ],
  notes: [],
  ytd_summary: {
    tax_year: currentYear,
    as_of_date: `${currentYear}-05-01`,
    remaining_pay_periods: 10,
    remaining_w2_pay_periods: 10,
    remaining_pension_periods: 5,
    remaining_non_taxable_periods: 5,
    employers: [
      {
        employer_id: 1,
        employer_name: "Test Corp",
        paychecks_recorded: 8,
        ytd_gross: "12000.00",
        ytd_pretax_deductions: "0.00",
        ytd_federal_withholding: "2000.00",
        projected_remaining_gross: "15000.00",
        projected_annual_gross: "27000.00",
      },
    ],
    ytd_pension_taxable: "0.00",
    ytd_pension_federal_withholding: "0.00",
    ytd_non_taxable_income: "0.00",
    ytd_total_federal_withholding: "2000.00",
  },
  projection_summary: {
    projected_remaining_pension_taxable: "0.00",
    projected_full_year_pension_taxable: "0.00",
    projected_full_year_non_taxable_income: "0.00",
    projected_remaining_w2_withholding: "3750.00",
    projected_remaining_pension_withholding: "0.00",
    projected_annual_w2_withholding: "5750.00",
    projected_annual_pension_withholding: "0.00",
    projected_annual_total_withholding: "5750.00",
  },
  assumptions: ["Used YTD average gross for remaining periods."],
};

const suggestionResponse = {
  tax_year: currentYear,
  as_of_date: `${currentYear}-05-10`,
  w2_pay_frequency: "semimonthly" as const,
  remaining_pay_periods: 16,
  remaining_pension_periods: 7,
  remaining_non_taxable_periods: 7,
  monthly_baseline_periods: 8,
  current_month_has_pension_entry: true,
  current_month_has_non_taxable_entry: true,
  notes: ["Backend suggestion response"],
};

describe("W4Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getConfig).mockResolvedValue({
      filing_status: "married_filing_jointly",
      num_children: 0,
      use_standard_deduction: true,
      itemized_deduction_amount: "0.00",
      age_65_plus: false,
      w2_pay_frequency: "monthly",
    });
    vi.mocked(apiClient.listEmployers).mockResolvedValue([
      {
        id: 1,
        name: "Test Corp",
        ein: null,
        start_date: "2026-01-01",
        end_date: null,
        notes: null,
      },
    ]);
    vi.mocked(apiClient.suggestMidyearPeriods).mockResolvedValue(suggestionResponse);
    vi.mocked(apiClient.optimizeMidyearW4).mockResolvedValue(midYearResponse);
  });

  it("switches to mid-year tab and submits optimization request", async () => {
    renderWithQueryClient();

    fireEvent.click(screen.getByRole("button", { name: "Mid-Year Optimizer" }));

    await waitFor(() => {
      expect(apiClient.suggestMidyearPeriods).toHaveBeenCalled();
    });

    const submitButton = screen.getByRole("button", {
      name: "Optimize Mid-Year W-4",
    });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(apiClient.optimizeMidyearW4).toHaveBeenCalledTimes(1);
    });

    const payload = vi.mocked(apiClient.optimizeMidyearW4).mock.calls[0]?.[0];
    expect(payload?.filing_status).toBe("married_filing_jointly");
    expect(payload?.remaining_pay_periods).toBeGreaterThan(0);
    expect(payload?.remaining_pension_periods).toBeGreaterThan(0);
    expect(payload?.remaining_non_taxable_periods).toBeGreaterThan(0);
    expect(payload?.as_of_date).toBeUndefined();
  });

  it("renders mid-year response details after successful optimization", async () => {
    renderWithQueryClient();

    fireEvent.click(screen.getByRole("button", { name: "Mid-Year Optimizer" }));
    fireEvent.click(screen.getByRole("button", { name: "Optimize Mid-Year W-4" }));

    await screen.findByRole("heading", { name: "Year-to-Date Summary" });

    expect(screen.getByText("W-2 Projection Summary")).toBeInTheDocument();
    expect(screen.getByText("Pension Projection Summary")).toBeInTheDocument();
    expect(screen.getByText("Non-taxable Projection Summary")).toBeInTheDocument();
    expect(screen.getByText("Projected Tax Rollup")).toBeInTheDocument();
    expect(screen.getByText("Assumptions")).toBeInTheDocument();
    expect(screen.getByText("Used YTD average gross for remaining periods.")).toBeInTheDocument();
  });

  it("auto-suggests editable split remaining periods", async () => {
    renderWithQueryClient();

    fireEvent.click(screen.getByRole("button", { name: "Mid-Year Optimizer" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Auto-suggest" })).toBeEnabled();
    });

    fireEvent.change(screen.getByLabelText("As-of date (optional)"), {
      target: { value: "2026-05-10" },
    });
    fireEvent.change(screen.getByLabelText("W-2 pay frequency"), {
      target: { value: "semimonthly" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Auto-suggest" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Remaining W-2 pay periods")).toHaveValue(16);
      expect(screen.getByLabelText("Remaining pension periods (monthly typical)")).toHaveValue(7);
      expect(screen.getByLabelText("Remaining non-taxable periods (monthly typical)")).toHaveValue(7);
    });
  });
});
