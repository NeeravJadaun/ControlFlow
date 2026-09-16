import { expect, test } from "@playwright/test";
import { DEMO_USERS, loginViaUI } from "./helpers";

test("dashboard tiles drill down into correctly filtered list views", async ({ page }) => {
  await loginViaUI(page, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);
  await page.goto("/");

  const criticalTile = page.locator(".stat-tile", { hasText: "Critical priority cases" });
  const criticalCount = Number((await criticalTile.locator(".value").innerText()).trim());
  await criticalTile.click();
  await page.waitForURL(/\/cases\?priority=critical/);
  await expect(page.getByText(`${criticalCount} total`)).toBeVisible();
  const priorityBadges = page.locator("tbody tr td:nth-child(4) .badge");
  const badgeCount = await priorityBadges.count();
  for (let i = 0; i < badgeCount; i++) {
    await expect(priorityBadges.nth(i)).toHaveText("critical");
  }

  await page.goto("/");
  const expiringTile = page.locator(".stat-tile", { hasText: "Documents expiring" });
  const expiringCount = Number((await expiringTile.locator(".value").innerText()).trim());
  await expiringTile.click();
  await page.waitForURL(/\/documents\?expiring_within_days=90/);
  await expect(page.getByText(`${expiringCount} total`)).toBeVisible();
});

test("cases page filter controls update the URL and result set together", async ({ page }) => {
  await loginViaUI(page, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);
  await page.goto("/cases");

  await page.locator(".filter-bar select").first().selectOption("resolved");
  await page.waitForURL(/status=resolved/);
  // The list re-fetches on filter change and shows a loading state in between,
  // so wait for the table to actually re-render before reading rows.
  await expect(page.locator("tbody tr").first()).toBeVisible();
  const statusBadges = page.locator("tbody tr td:nth-child(3) .badge");
  const count = await statusBadges.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) {
    await expect(statusBadges.nth(i)).toHaveText("resolved");
  }
});
