import { expect, test } from "@playwright/test";

test("create browser income, calculate taxes, and open projection and W-4 workflows", async ({
  page,
}) => {
  const unique = Date.now();
  await page.goto("/income");
  await expect(page.getByRole("heading", { name: "Income" })).toBeVisible();
  await page.getByRole("button", { name: "+ Add employer" }).click();
  await page.getByPlaceholder("Employer name").fill(`E2E Employer ${unique}`);
  await page.getByRole("button", { name: "Add employer" }).click();
  await page.getByRole("button", { name: "+ Add paycheck" }).click();
  await expect(page.getByRole("option", { name: `E2E Employer ${unique}` })).toBeAttached();
  await page.getByLabel("Pay date").fill("2026-07-15");
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
