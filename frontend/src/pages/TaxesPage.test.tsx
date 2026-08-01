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
