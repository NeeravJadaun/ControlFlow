export type Role = "operations_analyst" | "reviewer" | "compliance_officer" | "auditor" | "admin";

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type CaseStatus = "open" | "in_progress" | "pending_review" | "escalated" | "resolved" | "closed";
export type CasePriority = "low" | "medium" | "high" | "critical";

export interface CaseRecord {
  id: number;
  queue_id: number;
  entity_id: number | null;
  title: string;
  description: string | null;
  case_type: string;
  status: CaseStatus;
  priority: CasePriority;
  owner_id: number | null;
  due_at: string | null;
  sla_breached: boolean;
  escalation_level: number;
  resolution_evidence: string | null;
  resolved_at: string | null;
  tags: string[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CaseComment {
  id: number;
  case_id: number;
  author_id: number | null;
  body: string;
  created_at: string;
}

export interface CaseAttachment {
  id: number;
  case_id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_by_id: number;
  created_at: string;
}

export interface CaseQueue {
  id: number;
  key: string;
  name: string;
  description: string | null;
  default_sla_hours: number;
}

export type ReviewStatus = "draft" | "pending_review" | "approved" | "rejected" | "expired";

export interface DocumentRecord {
  id: number;
  document_type_id: number;
  entity_id: number;
  jurisdiction: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  version_number: number;
  review_status: ReviewStatus;
  approver_id: number | null;
  uploaded_by_id: number | null;
  file_ref: string | null;
  checksum: string | null;
  completeness_score: number;
  missing_fields: string[];
  is_duplicate_of_id: number | null;
  classification: Record<string, string>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentType {
  id: number;
  key: string;
  name: string;
  category: string;
  required_fields: string[];
  expiry_applicable: boolean;
  renewal_period_days: number | null;
}

export type EntityKind = "dealer" | "client" | "onboarding_record";

export interface EntityRecord {
  id: number;
  record_type_id: number;
  kind: EntityKind;
  name: string;
  external_ref: string | null;
  status: string;
  priority: string;
  owner_id: number | null;
  jurisdiction: string | null;
  tags: string[];
  attributes: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Account {
  id: number;
  entity_id: number;
  account_number: string;
  account_type: string;
  status: string;
  jurisdiction: string | null;
  attributes: Record<string, unknown>;
  version: number;
  created_at: string;
}

export interface Contact {
  id: number;
  entity_id: number;
  name: string;
  email: string | null;
  phone: string | null;
  role: string | null;
}

export type ControlFrequency = "daily" | "weekly" | "monthly" | "quarterly" | "annual";
export type ControlResult = "pass" | "fail";
export type RemediationStatus = "open" | "in_progress" | "resolved";

export interface Control {
  id: number;
  key: string;
  name: string;
  description: string | null;
  owner_id: number | null;
  reviewer_id: number | null;
  frequency: ControlFrequency;
  procedure: string | null;
  evidence_requirement: string | null;
  is_active: boolean;
}

export interface ControlTest {
  id: number;
  control_id: number;
  tester_id: number | null;
  reviewer_id: number | null;
  sample_ref: string | null;
  test_date: string;
  result: ControlResult;
  notes: string | null;
  evidence_ref: string | null;
  signed_off_by_id: number | null;
  signed_off_at: string | null;
  created_at: string;
}

export interface RemediationTask {
  id: number;
  control_test_id: number;
  description: string;
  owner_id: number | null;
  due_date: string | null;
  status: RemediationStatus;
  resolved_at: string | null;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  actor_id: number | null;
  timestamp: string;
  entity_type: string;
  entity_id: number;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  correlation_id: string | null;
}

export type RegimeType = "FATCA" | "CRS" | "QI";
export type ClassificationStatus =
  | "not_started"
  | "pending_documentation"
  | "documented"
  | "review_due"
  | "expired";

export interface Classification {
  id: number;
  entity_id: number;
  regime: RegimeType;
  status: ClassificationStatus;
  classification_value: string | null;
  effective_date: string | null;
  review_due_date: string | null;
}

export type DistributionKind = "fund_fact_sheet" | "maturity_notice";
export type DistributionStatus = "pending" | "sent" | "acknowledged" | "failed";

export interface Distribution {
  id: number;
  kind: DistributionKind;
  entity_id: number;
  account_id: number | null;
  reference_name: string;
  effective_date: string;
  status: DistributionStatus;
  channel: string;
  sent_at: string | null;
}

export interface WorkflowTransitionInfo {
  key: string;
  name: string;
  from_state: string;
  to_state: string;
  required_roles: string[];
  requires_approval: boolean;
  required_fields: string[];
}

export interface WorkflowStatus {
  workflow_key: string;
  entity_type: string;
  entity_id: number;
  current_state: string;
  available_transitions: WorkflowTransitionInfo[];
}

export interface DashboardSummary {
  cases: { open: number; overdue: number; by_priority: Record<string, number> };
  sla: { total_resolved: number; resolved_within_sla: number; attainment_rate: number };
  documents: {
    expiring_within_window: number;
    expired: number;
    renewal_buckets: Record<string, number>;
    window_days: number;
    by_document_type_id: Record<string, number>;
  };
  controls: {
    total_tests: number;
    passed: number;
    pass_rate: number;
    by_control: { key: string; name: string; total: number; passed: number; pass_rate: number }[];
  };
  remediation: Record<string, number>;
  exception_aging: Record<string, number>;
  workload: { owner_id: number; owner_name: string; open_cases: number }[];
}
