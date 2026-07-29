import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

    expect(screen.getByRole("heading", { name: "Federal Taxes" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Age 65+")).toBeChecked());
  });
});
