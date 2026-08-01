import { beforeEach, describe, expect, it } from "vitest";

import { browserStore, taxTrackerDatabase } from "./browserStore";

const csvFile = (contents: string, name = "import.csv") => {
  const file = new File([], name);
  Object.defineProperty(file, "text", { value: () => Promise.resolve(contents) });
  return file;
};

describe("browserStore", () => {
  beforeEach(async () => {
    await taxTrackerDatabase.delete();
    await taxTrackerDatabase.open();
  });

  it("cascades employer deletion to its paychecks", async () => {
    const employer = await browserStore.createEmployer({
      name: "Local Corp",
      start_date: "2026-01-01",
    });
    await browserStore.createPaycheck({
      employer_id: employer.id,
      pay_date: "2026-01-15",
      gross_wages: "1000",
    });

    await browserStore.deleteEmployer(employer.id);

    await expect(browserStore.listEmployers()).resolves.toEqual([]);
    await expect(browserStore.listPaychecks()).resolves.toEqual([]);
  });

  it("round-trips a complete portable backup", async () => {
    const employer = await browserStore.createEmployer({
      name: "Backup Corp",
      start_date: "2026-01-01",
    });
    await browserStore.createPaycheck({
      employer_id: employer.id,
      pay_date: "2026-01-15",
      gross_wages: "2500",
      deduction_401k: "250",
    });
    await browserStore.updateConfig({ filing_status: "single", num_children: 1 });
    const backup = await browserStore.exportBackup();

    await browserStore.deleteEmployer(employer.id);
    await browserStore.updateConfig({ num_children: 0 });
    await browserStore.importBackup(backup);

    await expect(browserStore.listEmployers()).resolves.toHaveLength(1);
    await expect(browserStore.listPaychecks()).resolves.toMatchObject([
      { gross_wages: "2500", total_pretax_deductions: "250.00" },
    ]);
    await expect(browserStore.getConfig()).resolves.toMatchObject({
      filing_status: "single",
      num_children: 1,
    });
  });

  it("reports duplicate CSV records instead of inserting them twice", async () => {
    const employer = await browserStore.createEmployer({
      name: "Import Corp",
      start_date: "2026-01-01",
    });
    const file = csvFile(
      `employer_id,pay_date,gross_wages\n${employer.id},2026-01-15,1000`,
      "paychecks.csv",
    );

    await expect(browserStore.importCsv("paychecks", file)).resolves.toMatchObject({
      imported: 1,
      skipped: 0,
    });
    await expect(browserStore.importCsv("paychecks", file)).resolves.toMatchObject({
      imported: 0,
      skipped: 1,
    });
    await expect(browserStore.listPaychecks()).resolves.toHaveLength(1);
  });

  it("imports legacy paycheck headings and creates employers by name", async () => {
    const file = csvFile(
      'employer_name,pay_date,gross_wages,federal_withholding,deduction_401k\nYurts,01/15/2026,"$2,500.00",300.00,125.00',
      "legion.csv",
    );

    await expect(browserStore.importCsv("paychecks", file)).resolves.toMatchObject({
      imported: 1,
      skipped: 0,
    });
    await expect(browserStore.listEmployers()).resolves.toMatchObject([
      { name: "Yurts", start_date: "2026-01-15" },
    ]);
    await expect(browserStore.listPaychecks(2026)).resolves.toMatchObject([
      {
        pay_date: "2026-01-15",
        gross_wages: "2500.00",
        federal_withholding: "300.00",
      },
    ]);
  });

  it("normalizes legacy pension dates so imported records appear in year filters", async () => {
    const file = csvFile(
      "pay_date,gross_amount,pretax_deductions,source_description\n1/1/2026,2628.00,171.14,Retirement Pay",
      "ussf.csv",
    );

    await expect(browserStore.importCsv("pensions", file)).resolves.toMatchObject({
      imported: 1,
      skipped: 0,
    });
    await expect(browserStore.listPensions(2026)).resolves.toMatchObject([
      { pay_date: "2026-01-01", gross_amount: "2628.00" },
    ]);
  });

  it("reports actionable validation errors without inserting invalid rows", async () => {
    const file = csvFile("pay_date,amount\nnot-a-date,4428.10", "va.csv");

    await expect(browserStore.importCsv("non-taxable", file)).resolves.toMatchObject({
      imported: 0,
      skipped: 1,
      errors: [{ row: 2, error: expect.stringContaining("Invalid date") }],
    });
    await expect(browserStore.listNonTaxableIncome()).resolves.toEqual([]);
  });
});
