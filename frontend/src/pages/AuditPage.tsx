import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { listAuditLog } from "../api/endpoints";

export function AuditPage() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const filters = {
    entity_type: params.get("entity_type") ?? undefined,
    page,
    page_size: 30,
  };

  const auditQuery = useQuery({ queryKey: ["audit-log", filters], queryFn: () => listAuditLog(filters) });

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
          <h1>Audit Log</h1>
          <p>
            Immutable record of every actor, action, and before/after state across the platform.
            Available to Auditor and Compliance Officer roles.
          </p>
        </div>
      </div>

      <div className="filter-bar">
        <select
          value={filters.entity_type ?? ""}
          onChange={(e) => updateFilter("entity_type", e.target.value || null)}
        >
          <option value="">All entity types</option>
          <option value="case">Case</option>
          <option value="document">Document</option>
          <option value="entity">Entity</option>
          <option value="control_test">Control test</option>
          <option value="remediation_task">Remediation task</option>
          <option value="classification">Classification</option>
          <option value="distribution">Distribution</option>
          <option value="user">User</option>
        </select>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {auditQuery.isLoading ? (
          <div className="loading-block">Loading audit log…</div>
        ) : auditQuery.isError ? (
          <div className="empty-state">
            You need the Auditor or Compliance Officer role to view the full audit log.
          </div>
        ) : auditQuery.data && auditQuery.data.items.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Entity</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Correlation ID</th>
              </tr>
            </thead>
            <tbody>
              {auditQuery.data.items.map((entry) => (
                <tr key={entry.id}>
                  <td>{new Date(entry.timestamp).toLocaleString()}</td>
                  <td>
                    {entry.entity_type} #{entry.entity_id}
                  </td>
                  <td>{entry.action}</td>
                  <td>{entry.actor_id ?? "system"}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 11 }}>{entry.correlation_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No audit entries match these filters.</div>
        )}
      </div>

      {auditQuery.data ? (
        <div className="pagination">
          <span>
            Page {auditQuery.data.page} — {auditQuery.data.total} total
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
            disabled={page * 30 >= auditQuery.data.total}
            onClick={() => updateFilter("page", String(page + 1))}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}
