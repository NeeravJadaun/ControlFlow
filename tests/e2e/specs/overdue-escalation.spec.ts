import { expect, test } from "@playwright/test";
import { DEMO_USERS, apiGet, apiLogin, loginViaUI } from "./helpers";

test("an overdue case can be escalated from the case detail page", async ({ page, request }) => {
  const token = await apiLogin(request, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);

  // Deterministic demo seed data always has overdue cases; find one dynamically
  // rather than hardcoding an id, so the test survives a re-seed.
  const overdue = await apiGet(
    request,
    token,
    "/api/cases?overdue_only=true&status=open&page_size=1",
  );
  test.skip(overdue.total === 0, "No overdue open case in the current seed to escalate");
  const targetCase = overdue.items[0];

  await loginViaUI(page, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);
  await page.goto(`/cases/${targetCase.id}`);

  await expect(page.locator(".badge").filter({ hasText: "failed" })).toBeVisible();

  await page.getByRole("button", { name: "Escalate", exact: true }).click();
  await expect(page.locator(".badge").first()).toHaveText("escalated");

  const detailsCard = page.locator(".card", { hasText: "Details" });
  await expect(detailsCard.getByText("1", { exact: true })).toBeVisible(); // escalation level

  const auditCard = page.locator(".card", { hasText: "Audit trail" });
  await expect(auditCard.getByText("escalate", { exact: true })).toBeVisible();
});

test("dashboard overdue tile drills down into the same overdue case list", async ({ page }) => {
  await loginViaUI(page, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);
  await page.goto("/");

  const overdueTile = page.locator(".stat-tile", { hasText: "Overdue cases" });
  const overdueCount = Number((await overdueTile.locator(".value").innerText()).trim());
  await overdueTile.click();

  await page.waitForURL(/\/cases\?overdue_only=true/);
  await expect(page.getByText(`${overdueCount} total`)).toBeVisible();
});
