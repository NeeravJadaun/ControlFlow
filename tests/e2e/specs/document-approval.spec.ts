import { expect, test } from "@playwright/test";
import { DEMO_USERS, apiGet, apiLogin, loginViaUI } from "./helpers";

test("analyst creates and submits a document, reviewer approves it", async ({
  page,
  request,
}) => {
  const analystToken = await apiLogin(
    request,
    DEMO_USERS.analyst.email,
    DEMO_USERS.analyst.password,
  );
  const entities = await apiGet(request, analystToken, "/api/entities?kind=client&page_size=1");
  const entity = entities.items[0];
  const docTypes = await apiGet(request, analystToken, "/api/documents/types");
  const docType = docTypes.find((t: { required_fields: string[] }) => t.required_fields.length > 0);

  await loginViaUI(page, DEMO_USERS.analyst.email, DEMO_USERS.analyst.password);
  await page.goto("/documents");
  await page.getByRole("button", { name: "New document" }).click();

  await page.getByLabel("Entity ID").fill(String(entity.id));
  await page.getByLabel("Document type").selectOption(String(docType.id));
  for (const field of docType.required_fields) {
    await page.getByLabel(field.replace(/_/g, " "), { exact: false }).check();
  }
  await page.getByRole("button", { name: "Create", exact: true }).click();

  await page.waitForURL(/\/documents\/\d+$/);
  await expect(page.locator(".badge").first()).toHaveText("draft");
  await expect(page.getByText("Completeness: 100%")).toBeVisible();

  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.locator(".badge").first()).toHaveText("pending review");

  const docUrl = page.url();
  const documentId = docUrl.match(/\/documents\/(\d+)/)![1];

  await page.getByRole("button", { name: "Sign out" }).click();
  await loginViaUI(page, DEMO_USERS.reviewer.email, DEMO_USERS.reviewer.password);
  await page.goto(`/documents/${documentId}`);

  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.locator(".badge").first()).toHaveText("approved");

  const auditCard = page.locator(".card", { hasText: "Audit trail" });
  await expect(auditCard.getByText("approve", { exact: true })).toBeVisible();
});
