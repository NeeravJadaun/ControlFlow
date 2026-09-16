import type { APIRequestContext, Page } from "@playwright/test";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export const DEMO_USERS = {
  admin: { email: "admin@controlflow.demo", password: "Admin123!" },
  complianceOfficer: { email: "compliance.officer@controlflow.demo", password: "Compliance123!" },
  reviewer: { email: "reviewer@controlflow.demo", password: "Reviewer123!" },
  auditor: { email: "auditor@controlflow.demo", password: "Auditor123!" },
  analyst: { email: "analyst@controlflow.demo", password: "Analyst123!" },
};

export async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  const resp = await request.post(`${API_URL}/api/auth/login`, { data: { email, password } });
  if (!resp.ok()) {
    throw new Error(`Login failed for ${email}: ${resp.status()} ${await resp.text()}`);
  }
  const body = await resp.json();
  return body.access_token as string;
}

export async function apiGet(request: APIRequestContext, token: string, path: string) {
  const resp = await request.get(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok()) throw new Error(`GET ${path} failed: ${resp.status()} ${await resp.text()}`);
  return resp.json();
}

export async function apiPost(
  request: APIRequestContext,
  token: string,
  path: string,
  data?: unknown,
) {
  const resp = await request.post(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    data,
  });
  if (!resp.ok()) throw new Error(`POST ${path} failed: ${resp.status()} ${await resp.text()}`);
  return resp.json();
}

export async function loginViaUI(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/", { timeout: 10_000 });
}
