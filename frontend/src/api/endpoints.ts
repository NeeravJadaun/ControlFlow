import { apiClient, downloadFile } from "./client";
import type {
  AuditLogEntry,
  CaseAttachment,
  CaseComment,
  CaseQueue,
  CaseRecord,
  Classification,
  Control,
  ControlTest,
  CurrentUser,
  DashboardSummary,
  Distribution,
  DocumentRecord,
  DocumentType,
  EntityRecord,
  Page,
  RemediationTask,
  Role,
  WorkflowStatus,
} from "../types";

// --- auth ---
export async function login(email: string, password: string) {
  const { data } = await apiClient.post<{
    access_token: string;
    role: Role;
    full_name: string;
    user_id: number;
  }>("/api/auth/login", { email, password });
  return data;
}

export async function me() {
  const { data } = await apiClient.get<CurrentUser>("/api/auth/me");
  return data;
}

// --- dashboards ---
export async function getDashboardSummary() {
  const { data } = await apiClient.get<DashboardSummary>("/api/dashboards/summary");
  return data;
}

export async function getSlaTrend(days = 180) {
  const { data } = await apiClient.get<
    { date: string; total: number; within_sla: number; attainment_rate: number }[]
  >("/api/dashboards/cases/sla-trend", { params: { days } });
  return data;
}

export async function getMonthlyTrend(months = 6) {
  const { data } = await apiClient.get<{ month: string; created: number; resolved: number }[]>(
    "/api/dashboards/cases/monthly-trend",
    { params: { months } },
  );
  return data;
}

// --- cases ---
export interface CaseListParams {
  queue_id?: number;
  status?: string;
  priority?: string;
  owner_id?: number;
  entity_id?: number;
  overdue_only?: boolean;
  open_only?: boolean;
  q?: string;
  page?: number;
  page_size?: number;
}

export async function listCases(params: CaseListParams = {}) {
  const { data } = await apiClient.get<Page<CaseRecord>>("/api/cases", { params });
  return data;
}

export async function getCase(id: number) {
  const { data } = await apiClient.get<CaseRecord>(`/api/cases/${id}`);
  return data;
}

export async function createCase(payload: {
  queue_id: number;
  entity_id?: number | null;
  title: string;
  description?: string;
  case_type?: string;
  priority?: string;
}) {
  const { data } = await apiClient.post<CaseRecord>("/api/cases", payload);
  return data;
}

export async function updateCase(id: number, payload: Record<string, unknown>) {
  const { data } = await apiClient.patch<CaseRecord>(`/api/cases/${id}`, payload);
  return data;
}

export async function startCase(id: number) {
  const { data } = await apiClient.post<CaseRecord>(`/api/cases/${id}/start`);
  return data;
}

export async function resolveCase(id: number, resolution_evidence: string, version: number) {
  const { data } = await apiClient.post<CaseRecord>(`/api/cases/${id}/resolve`, {
    resolution_evidence,
    version,
  });
  return data;
}

export async function escalateCase(id: number) {
  const { data } = await apiClient.post<CaseRecord>(`/api/cases/${id}/escalate`);
  return data;
}

export async function closeCase(id: number) {
  const { data } = await apiClient.post<CaseRecord>(`/api/cases/${id}/close`);
  return data;
}

export async function reopenCase(id: number) {
  const { data } = await apiClient.post<CaseRecord>(`/api/cases/${id}/reopen`);
  return data;
}

export async function submitCaseForReview(id: number) {
  const { data } = await apiClient.post<CaseRecord>(`/api/cases/${id}/submit-for-review`);
  return data;
}

export async function listCaseComments(id: number) {
  const { data } = await apiClient.get<CaseComment[]>(`/api/cases/${id}/comments`);
  return data;
}

export async function addCaseComment(id: number, body: string) {
  const { data } = await apiClient.post<CaseComment>(`/api/cases/${id}/comments`, { body });
  return data;
}

export async function listCaseAttachments(id: number) {
  const { data } = await apiClient.get<CaseAttachment[]>(`/api/cases/${id}/attachments`);
  return data;
}

export async function addCaseAttachment(
  id: number,
  payload: { filename: string; content_type?: string; size_bytes?: number },
) {
  const { data } = await apiClient.post<CaseAttachment>(`/api/cases/${id}/attachments`, payload);
  return data;
}

export async function bulkUpdateCases(payload: {
  case_ids: number[];
  status?: string;
  priority?: string;
  owner_id?: number;
}) {
  const { data } = await apiClient.post<CaseRecord[]>("/api/cases/bulk-update", payload);
  return data;
}

export async function listCaseQueues() {
  const { data } = await apiClient.get<CaseQueue[]>("/api/cases/queues");
  return data;
}

export function downloadCasesCsv() {
  return downloadFile("/api/cases/export.csv", "cases.csv");
}

export async function importCasesCsv(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<{ created: number; errors: string[] }>(
    "/api/cases/import",
    form,
  );
  return data;
}

// --- documents ---
export interface DocumentListParams {
  entity_id?: number;
  document_type_id?: number;
  review_status?: string;
  jurisdiction?: string;
  expiring_within_days?: number;
  page?: number;
  page_size?: number;
}

export async function listDocuments(params: DocumentListParams = {}) {
  const { data } = await apiClient.get<Page<DocumentRecord>>("/api/documents", { params });
  return data;
}

export async function getDocument(id: number) {
  const { data } = await apiClient.get<DocumentRecord>(`/api/documents/${id}`);
  return data;
}

export async function createDocument(payload: Record<string, unknown>) {
  const { data } = await apiClient.post<DocumentRecord>("/api/documents", payload);
  return data;
}

export async function submitDocument(id: number) {
  const { data } = await apiClient.post<DocumentRecord>(`/api/documents/${id}/submit`);
  return data;
}

export async function approveDocument(id: number, version: number, comment?: string) {
  const { data } = await apiClient.post<DocumentRecord>(`/api/documents/${id}/approve`, {
    version,
    comment,
  });
  return data;
}

export async function rejectDocument(id: number, version: number, reason: string) {
  const { data } = await apiClient.post<DocumentRecord>(`/api/documents/${id}/reject`, {
    version,
    reason,
  });
  return data;
}

export async function renewDocument(id: number, payload: Record<string, unknown>) {
  const { data } = await apiClient.post<DocumentRecord>(`/api/documents/${id}/renew`, payload);
  return data;
}

export function downloadDocumentsCsv() {
  return downloadFile("/api/documents/export.csv", "documents.csv");
}

// --- entities ---
export async function listEntities(
  params: { kind?: string; status?: string; jurisdiction?: string; q?: string; page?: number } = {},
) {
  const { data } = await apiClient.get<Page<EntityRecord>>("/api/entities", { params });
  return data;
}

export async function getEntity(id: number) {
  const { data } = await apiClient.get<EntityRecord>(`/api/entities/${id}`);
  return data;
}

export function downloadEntitiesCsv() {
  return downloadFile("/api/entities/export.csv", "entities.csv");
}

export async function importEntitiesCsv(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<{ created: number; errors: string[] }>(
    "/api/entities/import",
    form,
  );
  return data;
}

// --- controls ---
export async function listControls() {
  const { data } = await apiClient.get<Control[]>("/api/controls");
  return data;
}

export async function listControlTests(controlId: number) {
  const { data } = await apiClient.get<ControlTest[]>(`/api/controls/${controlId}/tests`);
  return data;
}

export async function recordControlTest(payload: {
  control_id: number;
  test_date: string;
  result: string;
  sample_ref?: string;
  notes?: string;
  evidence_ref?: string;
}) {
  const { data } = await apiClient.post<ControlTest>("/api/controls/tests", payload);
  return data;
}

export async function signOffControlTest(testId: number) {
  const { data } = await apiClient.post<ControlTest>(`/api/controls/tests/${testId}/sign-off`);
  return data;
}

export async function listRemediationTasks(status?: string) {
  const { data } = await apiClient.get<RemediationTask[]>("/api/controls/remediation-tasks", {
    params: { status },
  });
  return data;
}

export async function createRemediationTask(payload: {
  control_test_id: number;
  description: string;
  owner_id?: number;
  due_date?: string;
}) {
  const { data } = await apiClient.post<RemediationTask>("/api/controls/remediation-tasks", payload);
  return data;
}

export async function updateRemediationTask(id: number, status: string) {
  const { data } = await apiClient.patch<RemediationTask>(`/api/controls/remediation-tasks/${id}`, {
    status,
  });
  return data;
}

export function downloadEvidenceCsv() {
  return downloadFile("/api/controls/evidence/export.csv", "audit_evidence.csv");
}

// --- audit ---
export async function listAuditLog(
  params: { entity_type?: string; entity_id?: number; page?: number; page_size?: number } = {},
) {
  const { data } = await apiClient.get<Page<AuditLogEntry>>("/api/audit", { params });
  return data;
}

export async function getEntityAuditTrail(entityType: string, entityId: number) {
  const { data } = await apiClient.get<AuditLogEntry[]>(
    `/api/audit/entity/${entityType}/${entityId}`,
  );
  return data;
}

// --- financial ---
export async function listClassifications(
  params: {
    entity_id?: number;
    regime?: string;
    status?: string;
    page?: number;
    page_size?: number;
  } = {},
) {
  const { data } = await apiClient.get<Page<Classification>>("/api/financial/classifications", {
    params,
  });
  return data;
}

export async function listDistributions(
  params: {
    kind?: string;
    status?: string;
    entity_id?: number;
    page?: number;
    page_size?: number;
  } = {},
) {
  const { data } = await apiClient.get<Page<Distribution>>("/api/financial/distributions", {
    params,
  });
  return data;
}

export async function markDistributionSent(id: number) {
  const { data } = await apiClient.post<Distribution>(`/api/financial/distributions/${id}/mark-sent`);
  return data;
}

export async function acknowledgeDistribution(id: number) {
  const { data } = await apiClient.post<Distribution>(
    `/api/financial/distributions/${id}/acknowledge`,
  );
  return data;
}

// --- workflows ---
export async function getWorkflowStatus(workflowKey: string, entityType: string, entityId: number) {
  const { data } = await apiClient.get<WorkflowStatus>(
    `/api/workflows/${workflowKey}/${entityType}/${entityId}`,
  );
  return data;
}

// --- reference data ---
export async function listDocumentTypes() {
  const { data } = await apiClient.get<DocumentType[]>("/api/documents/types");
  return data;
}

export async function listRecordTypes() {
  const { data } = await apiClient.get<
    { id: number; key: string; name: string; description: string | null }[]
  >("/api/entities/record-types");
  return data;
}
