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

    expect(screen.getByRole("heading", { name: "W-2 Paychecks" })).toBeInTheDocument();
    expect(await screen.findByText(/No paychecks for/)).toBeInTheDocument();
  });
});

it("shows bonus-inclusive gross and pre-tax deductions beside federal taxable wages", async () => {
  const { browserStore, taxTrackerDatabase } = await import("../lib/storage/browserStore");
  await taxTrackerDatabase.delete();
  await taxTrackerDatabase.open();
  const employer = await browserStore.createEmployer({
    name: "Synthetic Bonus Corp",
    start_date: "2026-01-01",
  });
  const paycheck = await browserStore.createPaycheck({
    employer_id: employer.id,
    pay_date: "2026-01-15",
    gross_wages: "5000",
    bonus: "2000",
    deduction_401k: "700",
  });
  vi.mocked(apiClient.listEmployers).mockResolvedValue([employer]);
  vi.mocked(apiClient.listPaychecks).mockResolvedValue([paycheck]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <IncomePage />
    </QueryClientProvider>,
  );
  await screen.findByText("Synthetic Bonus Corp");
  expect(screen.getByRole("columnheader", { name: "Gross including bonuses" })).toBeInTheDocument();
  expect(screen.getAllByText("$7,000.00")).toHaveLength(2);
  expect(screen.getAllByText("$2,000.00")).toHaveLength(2);
  expect(screen.getAllByText("$700.00")).toHaveLength(2);
  expect(screen.getAllByText("$6,300.00")).toHaveLength(4); // taxable and net pay in the row and total
});

it("flags inconsistent bonus withholding without changing the saved paycheck", async () => {
  const { browserStore, taxTrackerDatabase } = await import("../lib/storage/browserStore");
  await taxTrackerDatabase.delete();
  await taxTrackerDatabase.open();
  const employer = await browserStore.createEmployer({
    name: "Synthetic Review Corp",
    start_date: "2026-01-01",
  });
  const paycheck = await browserStore.createPaycheck({
    employer_id: employer.id,
    pay_date: "2026-01-15",
    gross_wages: "5000",
    bonus: "2000",
    medicare: "72.50",
    social_security: "310",
  });
  vi.mocked(apiClient.listEmployers).mockResolvedValue([employer]);
  vi.mocked(apiClient.listPaychecks).mockResolvedValue([paycheck]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <IncomePage />
    </QueryClientProvider>,
  );
  await screen.findByText(/Check bonus or withholding entry:/);
  expect((await browserStore.listPaychecks(2026))[0].bonus).toBe("2000");
  expect((await browserStore.listPaychecks(2026))[0].gross_wages).toBe("5000");
});
