import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  createDocument,
  downloadDocumentsCsv,
  listDocumentTypes,
  listDocuments,
} from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function DocumentsPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [showNewDocument, setShowNewDocument] = useState(false);
  const page = Number(params.get("page") ?? "1");

  const filters = {
    review_status: params.get("review_status") ?? undefined,
    expiring_within_days: params.get("expiring_within_days")
      ? Number(params.get("expiring_within_days"))
      : undefined,
    page,
    page_size: 20,
  };

  const docsQuery = useQuery({ queryKey: ["documents", filters], queryFn: () => listDocuments(filters) });
  const docTypesQuery = useQuery({ queryKey: ["document-types"], queryFn: listDocumentTypes });

  function updateFilter(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("page", "1");
    setParams(next);
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Documents</h1>
          <p>
            Completeness checks, duplicate detection, and renewal reminders across tax forms, KYC
            packs, and classification certifications.
          </p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-sm" onClick={() => downloadDocumentsCsv()}>
            Export CSV
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowNewDocument(true)}>
            New document
          </button>
        </div>
      </div>

      {showNewDocument && docTypesQuery.data ? (
        <NewDocumentForm
          documentTypes={docTypesQuery.data}
          onClose={() => setShowNewDocument(false)}
          onCreated={(id) => {
            setShowNewDocument(false);
            navigate(`/documents/${id}`);
          }}
        />
      ) : null}

      <div className="filter-bar">
        <select
          value={filters.review_status ?? ""}
          onChange={(e) => updateFilter("review_status", e.target.value || null)}
        >
          <option value="">All statuses</option>
          {["draft", "pending_review", "approved", "rejected", "expired"].map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <select
          value={filters.expiring_within_days ?? ""}
          onChange={(e) => updateFilter("expiring_within_days", e.target.value || null)}
        >
          <option value="">Any expiry window</option>
          <option value="7">Expiring in 7 days</option>
          <option value="30">Expiring in 30 days</option>
          <option value="60">Expiring in 60 days</option>
          <option value="90">Expiring in 90 days</option>
        </select>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {docsQuery.isLoading ? (
          <div className="loading-block">Loading documents…</div>
        ) : docsQuery.data && docsQuery.data.items.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Entity</th>
                <th>Status</th>
                <th>Completeness</th>
                <th>Expiry</th>
                <th>Duplicate?</th>
              </tr>
            </thead>
            <tbody>
              {docsQuery.data.items.map((d) => (
                <tr key={d.id} className="clickable" onClick={() => navigate(`/documents/${d.id}`)}>
                  <td>#{d.id}</td>
                  <td>Entity {d.entity_id}</td>
                  <td>
                    <StatusBadge value={d.review_status} />
                  </td>
                  <td>{d.completeness_score}%</td>
                  <td>{d.expiry_date ?? "—"}</td>
                  <td>{d.is_duplicate_of_id ? `of #${d.is_duplicate_of_id}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No documents match these filters.</div>
        )}
      </div>

      {docsQuery.data ? (
        <div className="pagination">
          <span>
            Page {docsQuery.data.page} — {docsQuery.data.total} total
          </span>
          <button
            className="btn btn-sm"
            disabled={page <= 1}
            onClick={() => updateFilter("page", String(page - 1))}
          >
            Previous
          </button>
          <button
            className="btn btn-sm"
            disabled={page * 20 >= docsQuery.data.total}
            onClick={() => updateFilter("page", String(page + 1))}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}

function NewDocumentForm({
  documentTypes,
  onClose,
  onCreated,
}: {
  documentTypes: { id: number; key: string; name: string; required_fields: string[] }[];
  onClose: () => void;
  onCreated: (id: number) => void;
}) {
  const [entityId, setEntityId] = useState("");
  const [documentTypeId, setDocumentTypeId] = useState(documentTypes[0]?.id ?? 0);
  const [issueDate, setIssueDate] = useState(new Date().toISOString().slice(0, 10));
  const [providedFields, setProvidedFields] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const selectedType = documentTypes.find((t) => t.id === documentTypeId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const created = await createDocument({
        document_type_id: documentTypeId,
        entity_id: Number(entityId),
        issue_date: issueDate,
        provided_fields: providedFields,
      });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      onCreated(created.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <div className="card">
      <div className="section-title">New document</div>
      {error ? <div className="login-error">{error}</div> : null}
      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-3">
          <div className="form-row">
            <label htmlFor="new-doc-entity-id">Entity ID</label>
            <input
              id="new-doc-entity-id"
              type="number"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="new-doc-type">Document type</label>
            <select
              id="new-doc-type"
              value={documentTypeId}
              onChange={(e) => {
                setDocumentTypeId(Number(e.target.value));
                setProvidedFields({});
              }}
            >
              {documentTypes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="new-doc-issue-date">Issue date</label>
            <input
              id="new-doc-issue-date"
              type="date"
              value={issueDate}
              onChange={(e) => setIssueDate(e.target.value)}
            />
          </div>
        </div>
        {selectedType && selectedType.required_fields.length > 0 ? (
          <div className="form-row">
            <label>Required fields</label>
            <div className="checklist">
              {selectedType.required_fields.map((field) => (
                <label key={field}>
                  <input
                    type="checkbox"
                    checked={!!providedFields[field]}
                    onChange={(e) =>
                      setProvidedFields((prev) => ({ ...prev, [field]: e.target.checked }))
                    }
                  />
                  {field.replace(/_/g, " ")}
                </label>
              ))}
            </div>
          </div>
        ) : null}
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-primary" type="submit">
            Create
          </button>
          <button className="btn" type="button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
