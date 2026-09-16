import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  approveDocument,
  getDocument,
  getEntityAuditTrail,
  rejectDocument,
  submitDocument,
} from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../auth/AuthContext";

const REVIEWER_ROLES = ["reviewer", "compliance_officer", "admin"];

export function DocumentDetailPage() {
  const { id } = useParams();
  const docId = Number(id);
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);

  const docQuery = useQuery({ queryKey: ["document", docId], queryFn: () => getDocument(docId) });
  const auditQuery = useQuery({
    queryKey: ["document-audit", docId],
    queryFn: () => getEntityAuditTrail("document", docId),
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["document", docId] });
    queryClient.invalidateQueries({ queryKey: ["document-audit", docId] });
    queryClient.invalidateQueries({ queryKey: ["documents"] });
  }

  const submitMutation = useMutation({
    mutationFn: () => submitDocument(docId),
    onSuccess: invalidate,
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const approveMutation = useMutation({
    mutationFn: () => approveDocument(docId, docQuery.data!.version),
    onSuccess: invalidate,
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const rejectMutation = useMutation({
    mutationFn: () => rejectDocument(docId, docQuery.data!.version, rejectReason),
    onSuccess: () => {
      setShowReject(false);
      setRejectReason("");
      invalidate();
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  if (docQuery.isLoading) return <div className="loading-block">Loading document…</div>;
  if (!docQuery.data) return <div className="loading-block">Document not found.</div>;
  const d = docQuery.data;
  const canReview = user && REVIEWER_ROLES.includes(user.role);

  return (
    <div>
      <div className="breadcrumb">
        <Link to="/documents">← Back to documents</Link>
      </div>
      <div className="page-header">
        <div>
          <h1>Document #{d.id}</h1>
          <p>
            <StatusBadge value={d.review_status} /> &nbsp; Completeness: {d.completeness_score}%
          </p>
        </div>
        <div className="page-header-actions">
          {d.review_status === "draft" && d.completeness_score === 100 && (
            <button className="btn btn-sm" onClick={() => submitMutation.mutate()}>
              Submit for review
            </button>
          )}
          {d.review_status === "pending_review" && canReview && (
            <>
              <button className="btn btn-primary btn-sm" onClick={() => approveMutation.mutate()}>
                Approve
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => setShowReject(true)}>
                Reject
              </button>
            </>
          )}
        </div>
      </div>

      {error ? <div className="login-error">{error}</div> : null}

      {showReject ? (
        <div className="card">
          <div className="section-title">Reject document</div>
          <div className="form-row">
            <label htmlFor="reject-reason">Reason</label>
            <textarea
              id="reject-reason"
              rows={2}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-danger"
              disabled={!rejectReason.trim()}
              onClick={() => rejectMutation.mutate()}
            >
              Confirm rejection
            </button>
            <button className="btn" onClick={() => setShowReject(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {d.completeness_score < 100 ? (
        <div className="disclaimer-banner">
          Missing required fields: {d.missing_fields.join(", ")}
        </div>
      ) : null}
      {d.is_duplicate_of_id ? (
        <div className="disclaimer-banner">
          Possible duplicate of document #{d.is_duplicate_of_id} (same entity, type, and issue date).
        </div>
      ) : null}

      <div className="two-col">
        <div className="card">
          <div className="section-title">Details</div>
          <table>
            <tbody>
              <tr>
                <td>Entity</td>
                <td>#{d.entity_id}</td>
              </tr>
              <tr>
                <td>Jurisdiction</td>
                <td>{d.jurisdiction ?? "—"}</td>
              </tr>
              <tr>
                <td>Issue date</td>
                <td>{d.issue_date ?? "—"}</td>
              </tr>
              <tr>
                <td>Expiry date</td>
                <td>{d.expiry_date ?? "—"}</td>
              </tr>
              <tr>
                <td>Version</td>
                <td>{d.version_number}</td>
              </tr>
              <tr>
                <td>Checksum</td>
                <td style={{ fontFamily: "monospace", fontSize: 11 }}>{d.checksum?.slice(0, 16)}…</td>
              </tr>
            </tbody>
          </table>
          {Object.keys(d.classification).length > 0 ? (
            <>
              <div className="section-title" style={{ marginTop: 16 }}>
                Classification (educational, simplified)
              </div>
              <table>
                <tbody>
                  {Object.entries(d.classification).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : null}
        </div>

        <div className="card">
          <div className="section-title">Audit trail</div>
          {auditQuery.data && auditQuery.data.length > 0 ? (
            auditQuery.data.map((entry) => (
              <div className="comment" key={entry.id}>
                <div className="meta">{new Date(entry.timestamp).toLocaleString()}</div>
                <strong>{entry.action}</strong>
              </div>
            ))
          ) : (
            <div className="empty-state">No audit history.</div>
          )}
        </div>
      </div>
    </div>
  );
}
