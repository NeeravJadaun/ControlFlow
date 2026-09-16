import { expect, test } from "@playwright/test";
import { DEMO_USERS, loginViaUI } from "./helpers";

test("reviewer records a control test and a compliance officer signs it off", async ({ page }) => {
  await loginViaUI(page, DEMO_USERS.reviewer.email, DEMO_USERS.reviewer.password);
  await page.goto("/controls");

  await page.locator("tbody tr").first().click();
  await expect(page.getByText("Record control test")).toBeVisible();

  await page.getByLabel("Result").selectOption("fail");
  await page.getByLabel("Notes").fill("E2E-recorded exception for remediation demo.");
  await page.getByRole("button", { name: "Record test" }).click();

  const historyCard = page.locator(".card", { hasText: "Test history" });
  const firstRow = historyCard.locator("tbody tr").first();
  await expect(firstRow.getByText("fail")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await loginViaUI(page, DEMO_USERS.complianceOfficer.email, DEMO_USERS.complianceOfficer.password);
  await page.goto("/controls");
  await page.locator("tbody tr").first().click();

  const signOffButtons = page.getByRole("button", { name: "Sign off" });
  await expect(signOffButtons.first()).toBeVisible();
  const countBefore = await signOffButtons.count();
  await signOffButtons.first().click();
  await expect(signOffButtons).toHaveCount(countBefore - 1);
});
