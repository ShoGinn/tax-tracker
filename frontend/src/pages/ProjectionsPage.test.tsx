import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { ProjectionsPage } from "./ProjectionsPage";

vi.mock("../lib/api/client", () => ({
  apiClient: {
    projectYear: vi.fn(),
    compareYears: vi.fn(),
    getConfig: vi.fn(),
  },
}));

const currentYear = new Date().getFullYear();

const renderWithQueryClient = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectionsPage />
    </QueryClientProvider>,
  );
};

// Backend returns rates as plain percentages: effective_rate "18.89" means 18.89%, not 0.1889
const projectionResponse = {
  year: currentYear,
  filing_status: "single" as const,
  w2_gross: "80000.00",
  w2_taxable: "75000.00",
  pension_taxable: "0.00",
  total_taxable_income: "60400.00",
  taxable_income: "60400.00",
  federal_tax_liability: "8990.00",
  fica_liability: "6120.00",
  total_tax_liability: "15110.00",
  estimated_withholding: "0.00",
  estimated_refund_or_owed: "0.00",
  // Backend returns rates already as percentages — 18.89 means 18.89%
  effective_rate: "18.89",
  marginal_rate: "22",
};

describe("ProjectionsPage – rate display", () => {
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
    vi.mocked(apiClient.projectYear).mockResolvedValue(projectionResponse);
  });

  it("renders effective rate as a plain percentage (not multiplied by 100)", async () => {
    renderWithQueryClient();

    // Trigger form submission directly
    const form = document.querySelector("form");
    fireEvent.submit(form!);

    // Wait for result card to appear
    await waitFor(() => {
      expect(screen.getByText("Effective rate")).toBeInTheDocument();
    });

    const effectiveRow = screen.getByText("Effective rate");
    const effectiveValue = effectiveRow.closest(".result-row")?.querySelector("span:last-child");

    // Should show "18.89%" not "1889.00%"
    expect(effectiveValue?.textContent).toBe("18.89%");
    expect(effectiveValue?.textContent).not.toMatch(/1[89]\d{2}/);
  });

  it("renders marginal rate as a plain percentage (not multiplied by 100)", async () => {
    renderWithQueryClient();

    const form = document.querySelector("form");
    fireEvent.submit(form!);

    await waitFor(() => {
      expect(screen.getByText("Marginal rate")).toBeInTheDocument();
    });

    const marginalRow = screen.getByText("Marginal rate");
    const marginalValue = marginalRow.closest(".result-row")?.querySelector("span:last-child");

    // Should show "22%" not "2200%"
    expect(marginalValue?.textContent).toBe("22%");
    expect(marginalValue?.textContent).not.toMatch(/2200/);
  });

  it("renders total tax liability formatted as currency", async () => {
    renderWithQueryClient();

    const form = document.querySelector("form");
    fireEvent.submit(form!);

    await waitFor(() => {
      expect(screen.getByText("Total tax liability")).toBeInTheDocument();
    });
    expect(screen.getByText("$15,110.00")).toBeInTheDocument();
  });
});
