import { expect, test } from "@playwright/test";

test("create browser income, calculate taxes, and open projection and W-4 workflows", async ({
  page,
}) => {
  const unique = Date.now();
  const taxYear = new Date().getFullYear();
  await page.goto("/income");
  await expect(page.getByRole("heading", { name: "Income records" })).toBeVisible();
  await page.getByRole("button", { name: "+ Add employer" }).click();
  await page.getByPlaceholder("Employer name").fill(`E2E Employer ${unique}`);
  await page.getByRole("button", { name: "Add employer" }).click();
  await page.getByRole("button", { name: "+ Add paycheck" }).click();
  await expect(page.getByRole("option", { name: `E2E Employer ${unique}` })).toBeAttached();
  await page.getByLabel("Pay date").fill(`${taxYear}-07-15`);
  await page.getByLabel("Gross wages").fill("5000");
  await page.getByLabel("Fed. withholding").fill("650");
  await page.getByRole("button", { name: "Save paycheck" }).click();
  await expect(page.getByText("$5,000.00").first()).toBeVisible();

  await page.goto("/taxes");
  await page.getByLabel("W-2 gross wages").fill("60000");
  await page.getByRole("button", { name: "Calculate taxes" }).click();
  await expect(page.getByText("Federal tax liability")).toBeVisible();

  await page.goto("/projections");
  await expect(page.getByRole("heading", { name: "Future scenarios" })).toBeVisible();

  await page.goto("/w4");
  await expect(page.getByRole("heading", { name: "Withholding plan" })).toBeVisible();
});

test("import a paycheck CSV using an employer name", async ({ page }) => {
  const taxYear = new Date().getFullYear();
  const employer = `CSV Employer ${Date.now()}`;
  const csv = [
    "employer_name,pay_date,gross_wages,federal_withholding,social_security,medicare",
    `${employer},01/15/${taxYear},2500.00,300.00,155.00,36.25`,
  ].join("\n");

  await page.goto("/imports");
  await expect(page.getByRole("heading", { name: "Import records" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download example CSV" })).toHaveAttribute(
    "download",
    "paychecks_example.csv",
  );

  await page.locator('input[type="file"]').setInputFiles({
    name: "paychecks.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.locator(".csv-result")).toContainText("Imported: 1");
  await expect(page.locator(".csv-result")).toContainText("Skipped: 0");

  await page.goto("/income");
  const importedRow = page.getByRole("row").filter({ hasText: employer });
  await expect(importedRow).toContainText(`${taxYear}-01-15`);
  await expect(importedRow).toContainText("$2,500.00");
});

test("overview and reconciliation show federal balances and valid brackets", async ({ page }) => {
  const year = new Date().getFullYear();
  await page.goto("/imports");
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-paychecks.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      `employer_name,pay_date,gross_wages,federal_withholding,social_security,medicare\nSynthetic Corp,01/15/${year},60000,10000,3720,870`,
    ),
  });
  await page.getByRole("button", { name: "Import", exact: true }).click();
  await expect(page.locator(".csv-result")).toContainText("Imported: 1");
  await page.goto("/");
  await expect(page.locator(".plan-status-value")).not.toHaveText("$0.00");
  await expect(page.locator(".plan-status-detail")).toContainText("projected federal withholding");
  await expect(page.getByText("Projected payroll taxes (FICA)")).toBeVisible();
  await page.goto("/taxes");
  await page.getByRole("button", { name: "Reconciliation from DB" }).click();
  await page.getByRole("button", { name: "Run reconciliation" }).click();
  await expect(page.getByText("Estimated federal refund")).toBeVisible();
  await page.getByRole("button", { name: "Show bracket breakdown" }).click();
  await expect(page.locator(".data-table")).not.toContainText("NaN");
  await expect(page.locator(".data-table tbody tr")).toHaveCount(2);
  await expect(page.getByText("$4,590.00", { exact: true }).first()).toBeVisible();
});

test("bonus paychecks show consistent gross, deductions, and taxable wages", async ({ page }) => {
  const year = new Date().getFullYear();
  await page.goto("/imports");
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-bonus.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      `employer_name,pay_date,gross_wages,bonus,deduction_401k\nSynthetic Bonus Corp,01/15/${year},5000,2000,700`,
    ),
  });
  await page.getByRole("button", { name: "Import", exact: true }).click();
  await expect(page.locator(".csv-result")).toContainText("Imported: 1");
  await page.goto("/income");
  await expect(page.getByRole("columnheader", { name: "Gross including bonuses" })).toBeVisible();
  const row = page.getByRole("row").filter({ hasText: "Synthetic Bonus Corp" });
  await expect(row).toContainText("$7,000.00");
  await expect(row).toContainText("$2,000.00");
  await expect(row).toContainText("$700.00");
  await expect(row).toContainText("$6,300.00");
  await expect(page.locator("tfoot")).toContainText("$7,000.00");
  await expect(page.locator("tfoot")).toContainText("$6,300.00");
});
