import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { W4Page } from "./W4Page";

vi.mock("../lib/api/client", () => ({
  apiClient: {
    optimizeW4: vi.fn(),
    optimizeMidyearW4: vi.fn(),
    calculateWithholding: vi.fn(),
    listEmployers: vi.fn(),
  },
}));

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
  year: 2026,
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
    tax_year: 2026,
    as_of_date: "2026-05-01",
    remaining_pay_periods: 10,
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
  },
  assumptions: ["Used YTD average gross for remaining periods."],
};

describe("W4Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
    vi.mocked(apiClient.optimizeMidyearW4).mockResolvedValue(midYearResponse);
  });

  it("switches to mid-year tab and submits optimization request", async () => {
    renderWithQueryClient();

    fireEvent.click(screen.getByRole("button", { name: "Mid-Year Optimizer" }));

    const submitButton = screen.getByRole("button", { name: "Optimize Mid-Year W-4" });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(apiClient.optimizeMidyearW4).toHaveBeenCalledTimes(1);
    });

    const payload = vi.mocked(apiClient.optimizeMidyearW4).mock.calls[0]?.[0];
    expect(payload?.filing_status).toBe("single");
    expect(payload?.remaining_pay_periods).toBe(10);
    expect(payload?.as_of_date).toBeUndefined();
  });

  it("renders mid-year response details after successful optimization", async () => {
    renderWithQueryClient();

    fireEvent.click(screen.getByRole("button", { name: "Mid-Year Optimizer" }));
    fireEvent.click(screen.getByRole("button", { name: "Optimize Mid-Year W-4" }));

    await screen.findByRole("heading", { name: "Year-to-Date Summary" });

    expect(screen.getByText("Employer Breakdown")).toBeInTheDocument();
    expect(screen.getByText("Projection Summary")).toBeInTheDocument();
    expect(screen.getByText("Assumptions")).toBeInTheDocument();
    expect(screen.getByText("Used YTD average gross for remaining periods.")).toBeInTheDocument();
  });
});
