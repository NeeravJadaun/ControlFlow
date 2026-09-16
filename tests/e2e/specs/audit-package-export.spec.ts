import { expect, test } from "@playwright/test";
import { DEMO_USERS, apiGet, apiLogin, apiPost, loginViaUI } from "./helpers";

test("auditor can export the control-test evidence package as CSV", async ({ page }) => {
  await loginViaUI(page, DEMO_USERS.auditor.email, DEMO_USERS.auditor.password);
  await page.goto("/controls");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export audit evidence" }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toBe("audit_evidence.csv");
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  await new Promise<void>((resolve, reject) => {
    stream.on("data", (chunk) => chunks.push(chunk as Buffer));
    stream.on("end", () => resolve());
    stream.on("error", reject);
  });
  const content = Buffer.concat(chunks).toString("utf-8");
  expect(content.split("\n")[0]).toContain("control_key");
  expect(content.length).toBeGreaterThan(50);
});

test("operations analyst cannot see the full audit log", async ({ page }) => {
  await loginViaUI(page, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);
  await page.goto("/audit");
  await expect(
    page.getByText("You need the Auditor or Compliance Officer role"),
  ).toBeVisible();
});

test("auditor can browse the full immutable audit log", async ({ page, request }) => {
  // Guarantee at least one audit row exists regardless of test execution order
  // or how recently the demo data was reseeded.
  const adminToken = await apiLogin(request, DEMO_USERS.admin.email, DEMO_USERS.admin.password);
  const recordTypes = await apiGet(request, adminToken, "/api/entities/record-types");
  await apiPost(request, adminToken, "/api/entities", {
    record_type_id: recordTypes[0].id,
    kind: "client",
    name: "E2E Audit Log Seed Entity",
  });

  await loginViaUI(page, DEMO_USERS.auditor.email, DEMO_USERS.auditor.password);
  await page.goto("/audit");
  await expect(page.locator("table")).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible();
});
