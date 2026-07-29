import { beforeEach, describe, expect, it } from "vitest";

import { browserStore, taxTrackerDatabase } from "./browserStore";

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
    const file = new File([], "paychecks.csv");
    Object.defineProperty(file, "text", {
      value: () =>
        Promise.resolve(`employer_id,pay_date,gross_wages\n${employer.id},2026-01-15,1000`),
    });

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
});
