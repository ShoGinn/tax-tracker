import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { apiClient } from "../lib/api/client";
import { IncomePage } from "./IncomePage";

vi.mock("../lib/api/client", () => ({
  apiClient: {
    listEmployers: vi.fn(),
    listPaychecks: vi.fn(),
    createEmployer: vi.fn(),
    createPaycheck: vi.fn(),
    deletePaycheck: vi.fn(),
  },
}));

describe("IncomePage", () => {
  it("renders the empty paycheck workflow", async () => {
    vi.mocked(apiClient.listEmployers).mockResolvedValue([]);
    vi.mocked(apiClient.listPaychecks).mockResolvedValue([]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <IncomePage />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Income" })).toBeInTheDocument();
    expect(await screen.findByText(/No paychecks for/)).toBeInTheDocument();
  });
});
