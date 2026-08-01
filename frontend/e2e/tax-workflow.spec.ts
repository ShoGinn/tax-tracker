import { expect, test } from "@playwright/test";

test("create browser income, calculate taxes, and open projection and W-4 workflows", async ({
  page,
}) => {
  const unique = Date.now();
  const taxYear = new Date().getFullYear();
  await page.goto("/income");
  await expect(page.getByRole("heading", { name: "Income" })).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "Projections" })).toBeVisible();

  await page.goto("/w4");
  await expect(page.getByRole("heading", { name: "W-4 Optimization" })).toBeVisible();
});

test("import a paycheck CSV using an employer name", async ({ page }) => {
  const taxYear = new Date().getFullYear();
  const employer = `CSV Employer ${Date.now()}`;
  const csv = [
    "employer_name,pay_date,gross_wages,federal_withholding,social_security,medicare",
    `${employer},01/15/${taxYear},2500.00,300.00,155.00,36.25`,
  ].join("\n");

  await page.goto("/imports");
  await expect(page.getByRole("heading", { name: "CSV Import" })).toBeVisible();
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
