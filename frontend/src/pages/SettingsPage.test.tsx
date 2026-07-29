import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { SettingsPage } from "./SettingsPage";

vi.mock("../lib/api/client", () => ({
  apiClient: { getConfig: vi.fn(), updateConfig: vi.fn() },
}));

const config = {
  filing_status: "single" as const,
  num_children: 0,
  use_standard_deduction: true,
  itemized_deduction_amount: "0",
  age_65_plus: false,
  w2_pay_frequency: "monthly" as const,
};

describe("SettingsPage", () => {
  it("loads and persists age and dependent settings", async () => {
    vi.mocked(apiClient.getConfig).mockResolvedValue(config);
    vi.mocked(apiClient.updateConfig).mockResolvedValue({
      ...config,
      num_children: 2,
      age_65_plus: true,
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <SettingsPage />
      </QueryClientProvider>,
    );

    await userEvent.clear(await screen.findByLabelText("Qualifying Children"));
    await userEvent.type(screen.getByLabelText("Qualifying Children"), "2");
    await userEvent.click(screen.getByLabelText(/Age 65 or older/));
    await userEvent.click(screen.getByRole("button", { name: "Save Settings" }));

    await waitFor(() =>
      expect(apiClient.updateConfig).toHaveBeenCalledWith(
        expect.objectContaining({ num_children: 2, age_65_plus: true }),
      ),
    );
  });
});
