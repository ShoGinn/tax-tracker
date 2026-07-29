import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { CsvImportPage } from "./CsvImportPage";

vi.mock("../lib/api/client", () => ({
  apiClient: { importCsv: vi.fn() },
}));

describe("CsvImportPage", () => {
  it("uploads through the shared client and explains skipped duplicates", async () => {
    vi.mocked(apiClient.importCsv).mockResolvedValue({
      imported: 1,
      skipped: 1,
      total_rows: 2,
      errors: [{ row: 3, error: "Duplicate entry", data: {} }],
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <CsvImportPage />
      </QueryClientProvider>,
    );
    const file = new File(["pay_date,gross_wages\n2026-01-01,1000"], "paychecks.csv", {
      type: "text/csv",
    });
    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();
    fireEvent.change(input!, { target: { files: [file] } });

    await userEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(apiClient.importCsv).toHaveBeenCalledWith("paychecks", file));
    expect(screen.getByText(/Duplicate records are skipped safely/)).toBeInTheDocument();
  });
});
