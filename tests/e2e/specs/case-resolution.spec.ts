import { expect, test } from "@playwright/test";
import { DEMO_USERS, apiGet, apiLogin, apiPost, loginViaUI } from "./helpers";

test("analyst can start and resolve a case, and the resolution is reflected everywhere", async ({
  page,
  request,
}) => {
  const token = await apiLogin(request, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);
  const queues = await apiGet(request, token, "/api/cases/queues");
  const queue = queues[0];

  const created = await apiPost(request, token, "/api/cases", {
    queue_id: queue.id,
    title: "E2E case resolution test",
    priority: "medium",
  });

  await loginViaUI(page, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);
  await page.goto(`/cases/${created.id}`);

  const statusBadge = page.locator(".badge").first();
  await expect(statusBadge).toHaveText("open");

  await page.getByRole("button", { name: "Start work" }).click();
  await expect(statusBadge).toHaveText("in progress");

  await page.getByRole("button", { name: "Resolve", exact: true }).click();
  await page
    .getByPlaceholder("Describe how this case was resolved…")
    .fill("Confirmed with the client via recorded call; documentation attached.");
  await page.getByRole("button", { name: "Confirm resolution" }).click();

  await expect(statusBadge).toHaveText("resolved");
  await expect(page.getByText("Confirmed with the client via recorded call")).toBeVisible();

  const detailsCard = page.locator(".card", { hasText: "Details" });
  await expect(detailsCard.getByText("resolved", { exact: true })).toBeVisible();

  const auditCard = page.locator(".card", { hasText: "Audit trail" });
  await expect(auditCard.getByText("resolve", { exact: true })).toBeVisible();
});
