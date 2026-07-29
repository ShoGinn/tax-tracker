import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiClient } from "./client";
import { taxTrackerDatabase } from "../storage/browserStore";

const jsonResponse = (body: unknown = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

describe("apiClient", () => {
  beforeEach(async () => {
    await taxTrackerDatabase.delete();
    await taxTrackerDatabase.open();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(jsonResponse())),
    );
  });

  it("maps the public client methods to the backend contract", async () => {
    await apiClient.getAvailableYears();
    await apiClient.calculateTaxes({ filing_status: "single" });
    await apiClient.calculateFromDb(2026, {
      filing_status: "single",
      num_children: 0,
      use_standard_deduction: true,
      itemized_deduction_amount: 0,
    });
    await apiClient.listEmployers();
    const employer = await apiClient.createEmployer({ name: "Test", start_date: "2026-01-01" });
    await apiClient.updateEmployer(employer.id, { name: "Updated" });
    await apiClient.listPaychecks(2026);
    const paycheck = await apiClient.createPaycheck({
      employer_id: employer.id,
      pay_date: "2026-01-01",
      gross_wages: "1000",
    });
    await apiClient.updatePaycheck(paycheck.id, { gross_wages: "1100" });
    await apiClient.deletePaycheck(paycheck.id);
    await apiClient.listPensions(2026);
    const pension = await apiClient.createPension({ pay_date: "2026-01-01", gross_amount: "500" });
    await apiClient.updatePension(pension.id, { gross_amount: "550" });
    await apiClient.deletePension(pension.id);
    await apiClient.listNonTaxableIncome(2026);
    const nonTaxable = await apiClient.createNonTaxableIncome({
      pay_date: "2026-01-01",
      amount: "400",
    });
    await apiClient.updateNonTaxableIncome(nonTaxable.id, { amount: "450" });
    await apiClient.deleteNonTaxableIncome(nonTaxable.id);
    await apiClient.deleteEmployer(employer.id);
    await apiClient.optimizeW4({
      total_annual_w2_income: "60000",
      paychecks_per_year: 26,
      filing_status: "single",
    });
    await apiClient.suggestMidyearPeriods({
      tax_year: 2026,
      w2_pay_frequency: "biweekly",
    });
    await apiClient.optimizeMidyearW4({
      tax_year: 2026,
      filing_status: "single",
      remaining_pay_periods: 10,
    });
    await apiClient.calculateWithholding({
      gross_pay_per_paycheck: "2000",
      pay_frequency: "biweekly",
      filing_status: "single",
    });
    await apiClient.projectYear({ filing_status: "single" });
    await apiClient.compareYears({
      filing_status: "single",
      base_w2_gross: "50000",
      comparison_w2_gross: "55000",
    });
    await apiClient.getDashboardProjection(2026);
    await apiClient.getConfig();
    await apiClient.updateConfig({ num_children: 1 });

    const calls = vi.mocked(fetch).mock.calls;
    const contracts = calls.map(([url, init]) => {
      const parsed = new URL(String(url));
      return `${init?.method ?? "GET"} ${parsed.pathname}`;
    });

    expect(contracts).toEqual([
      "GET /taxes/tax-data/available-years",
      "POST /taxes/calculate",
      "POST /taxes/reconcile-records/2026",
      "POST /w4/optimize",
      "POST /w4/suggest-periods",
      "POST /w4/optimize-midyear",
      "POST /w4/calculate-withholding",
      "POST /projections/project-year",
      "POST /projections/compare-years",
      "POST /projections/dashboard/2026",
    ]);
  });

  it("imports CSV directly into browser storage", async () => {
    const employer = await apiClient.createEmployer({ name: "Test", start_date: "2026-01-01" });
    const file = new File([], "paychecks.csv");
    Object.defineProperty(file, "text", {
      value: () =>
        Promise.resolve(`employer_id,pay_date,gross_wages\n${employer.id},2026-01-01,1000`),
    });
    const result = await apiClient.importCsv("paychecks", file);

    expect(result).toMatchObject({ imported: 1, skipped: 0 });
    await expect(apiClient.listPaychecks(2026)).resolves.toHaveLength(1);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("raises a status-aware error using the backend detail", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Invalid tax year" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const error = await apiClient.getAvailableYears().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Invalid tax year", status: 400 });
  });
});
