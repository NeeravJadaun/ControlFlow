import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  addCaseComment,
  closeCase,
  escalateCase,
  getCase,
  getEntityAuditTrail,
  getWorkflowStatus,
  listCaseAttachments,
  listCaseComments,
  reopenCase,
  resolveCase,
  startCase,
  submitCaseForReview,
} from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function CaseDetailPage() {
  const { id } = useParams();
  const caseId = Number(id);
  const queryClient = useQueryClient();
  const [commentBody, setCommentBody] = useState("");
  const [resolutionEvidence, setResolutionEvidence] = useState("");
  const [showResolveForm, setShowResolveForm] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const caseQuery = useQuery({ queryKey: ["case", caseId], queryFn: () => getCase(caseId) });
  const commentsQuery = useQuery({
    queryKey: ["case-comments", caseId],
    queryFn: () => listCaseComments(caseId),
  });
  const attachmentsQuery = useQuery({
    queryKey: ["case-attachments", caseId],
    queryFn: () => listCaseAttachments(caseId),
  });
  const workflowQuery = useQuery({
    queryKey: ["case-workflow", caseId],
    queryFn: () => getWorkflowStatus("case-lifecycle", "case", caseId),
  });
  const auditQuery = useQuery({
    queryKey: ["case-audit", caseId],
    queryFn: () => getEntityAuditTrail("case", caseId),
  });

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ["case", caseId] });
    queryClient.invalidateQueries({ queryKey: ["case-workflow", caseId] });
    queryClient.invalidateQueries({ queryKey: ["case-audit", caseId] });
    queryClient.invalidateQueries({ queryKey: ["cases"] });
  }

  const startMutation = useMutation({
    mutationFn: () => startCase(caseId),
    onSuccess: invalidateAll,
    onError: (e) => setActionError(apiErrorMessage(e)),
  });
  const submitMutation = useMutation({
    mutationFn: () => submitCaseForReview(caseId),
    onSuccess: invalidateAll,
    onError: (e) => setActionError(apiErrorMessage(e)),
  });
  const escalateMutation = useMutation({
    mutationFn: () => escalateCase(caseId),
    onSuccess: invalidateAll,
    onError: (e) => setActionError(apiErrorMessage(e)),
  });
  const closeMutation = useMutation({
    mutationFn: () => closeCase(caseId),
    onSuccess: invalidateAll,
    onError: (e) => setActionError(apiErrorMessage(e)),
  });
  const reopenMutation = useMutation({
    mutationFn: () => reopenCase(caseId),
    onSuccess: invalidateAll,
    onError: (e) => setActionError(apiErrorMessage(e)),
  });
  const resolveMutation = useMutation({
    mutationFn: () => resolveCase(caseId, resolutionEvidence, caseQuery.data!.version),
    onSuccess: () => {
      setShowResolveForm(false);
      setResolutionEvidence("");
      invalidateAll();
    },
    onError: (e) => setActionError(apiErrorMessage(e)),
  });
  const commentMutation = useMutation({
    mutationFn: () => addCaseComment(caseId, commentBody),
    onSuccess: () => {
      setCommentBody("");
      queryClient.invalidateQueries({ queryKey: ["case-comments", caseId] });
    },
  });

  if (caseQuery.isLoading) return <div className="loading-block">Loading case…</div>;
  if (!caseQuery.data) return <div className="loading-block">Case not found.</div>;
  const c = caseQuery.data;
  const transitions = workflowQuery.data?.available_transitions.map((t) => t.key) ?? [];

  return (
    <div>
      <div className="breadcrumb">
        <Link to="/cases">← Back to cases</Link>
      </div>
      <div className="page-header">
        <div>
          <h1>
            #{c.id} {c.title}
          </h1>
          <p>
            <StatusBadge value={c.status} /> &nbsp;
            <StatusBadge value={c.priority} /> &nbsp;
            {c.sla_breached ? <StatusBadge value="failed" /> : null}
          </p>
        </div>
        <div className="page-header-actions">
          {transitions.includes("start") && (
            <button className="btn btn-sm" onClick={() => startMutation.mutate()}>
              Start work
            </button>
          )}
          {transitions.includes("submit_for_review") && (
            <button className="btn btn-sm" onClick={() => submitMutation.mutate()}>
              Submit for review
            </button>
          )}
          {transitions.includes("resolve") && (
            <button className="btn btn-primary btn-sm" onClick={() => setShowResolveForm(true)}>
              Resolve
            </button>
          )}
          {transitions.includes("escalate") && (
            <button className="btn btn-sm" onClick={() => escalateMutation.mutate()}>
              Escalate
            </button>
          )}
          {transitions.includes("close") && (
            <button className="btn btn-sm" onClick={() => closeMutation.mutate()}>
              Close
            </button>
          )}
          {transitions.includes("reopen") && (
            <button className="btn btn-sm" onClick={() => reopenMutation.mutate()}>
              Reopen
            </button>
          )}
        </div>
      </div>

      {actionError ? <div className="login-error">{actionError}</div> : null}

      {showResolveForm ? (
        <div className="card">
          <div className="section-title">Resolve case</div>
          <div className="form-row">
            <label htmlFor="resolution-evidence">Resolution evidence</label>
            <textarea
              id="resolution-evidence"
              rows={3}
              value={resolutionEvidence}
              onChange={(e) => setResolutionEvidence(e.target.value)}
              placeholder="Describe how this case was resolved…"
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-primary"
              disabled={!resolutionEvidence.trim()}
              onClick={() => resolveMutation.mutate()}
            >
              Confirm resolution
            </button>
            <button className="btn" onClick={() => setShowResolveForm(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      <div className="two-col">
        <div>
          <div className="card">
            <div className="section-title">Details</div>
            <p style={{ margin: 0, color: "var(--color-text-muted)" }}>
              {c.description || "No description provided."}
            </p>
            <table style={{ marginTop: 12 }}>
              <tbody>
                <tr>
                  <td>Case type</td>
                  <td>{c.case_type}</td>
                </tr>
                <tr>
                  <td>Due</td>
                  <td>{c.due_at ? new Date(c.due_at).toLocaleString() : "—"}</td>
                </tr>
                <tr>
                  <td>Escalation level</td>
                  <td>{c.escalation_level}</td>
                </tr>
                <tr>
                  <td>Resolution evidence</td>
                  <td>{c.resolution_evidence || "—"}</td>
                </tr>
                <tr>
                  <td>Workflow state</td>
                  <td>{workflowQuery.data?.current_state ?? "—"}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="card">
            <div className="section-title">Comments</div>
            {commentsQuery.data?.map((comment) => (
              <div className="comment" key={comment.id}>
                <div className="meta">{new Date(comment.created_at).toLocaleString()}</div>
                {comment.body}
              </div>
            ))}
            <div className="form-row" style={{ marginTop: 10 }}>
              <textarea
                rows={2}
                placeholder="Add a comment…"
                value={commentBody}
                onChange={(e) => setCommentBody(e.target.value)}
              />
            </div>
            <button
              className="btn btn-sm"
              disabled={!commentBody.trim()}
              onClick={() => commentMutation.mutate()}
            >
              Add comment
            </button>
          </div>

          <div className="card">
            <div className="section-title">Attachments</div>
            {attachmentsQuery.data && attachmentsQuery.data.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Size</th>
                    <th>Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  {attachmentsQuery.data.map((a) => (
                    <tr key={a.id}>
                      <td>{a.filename}</td>
                      <td>{a.size_bytes} bytes</td>
                      <td>{new Date(a.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state">No attachments yet.</div>
            )}
          </div>
        </div>

        <div>
          <div className="card">
            <div className="section-title">Audit trail</div>
            {auditQuery.data && auditQuery.data.length > 0 ? (
              auditQuery.data.map((entry) => (
                <div className="comment" key={entry.id}>
                  <div className="meta">{new Date(entry.timestamp).toLocaleString()}</div>
                  <strong>{entry.action}</strong>
                  {entry.before || entry.after ? (
                    <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                      {entry.before ? `before: ${JSON.stringify(entry.before)}` : ""}
                      {entry.after ? ` after: ${JSON.stringify(entry.after)}` : ""}
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              <div className="empty-state">No audit history.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
