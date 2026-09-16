import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  bulkUpdateCases,
  downloadCasesCsv,
  createCase,
  importCasesCsv,
  listCaseQueues,
  listCases,
} from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function CasesPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<number[]>([]);
  const [showNewCase, setShowNewCase] = useState(false);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const page = Number(params.get("page") ?? "1");
  const filters = {
    status: params.get("status") ?? undefined,
    priority: params.get("priority") ?? undefined,
    overdue_only: params.get("overdue_only") === "true" ? true : undefined,
    open_only: params.get("open_only") === "true" ? true : undefined,
    q: params.get("q") ?? undefined,
    page,
    page_size: 20,
  };

  const casesQuery = useQuery({
    queryKey: ["cases", filters],
    queryFn: () => listCases(filters),
  });
  const queuesQuery = useQuery({ queryKey: ["case-queues"], queryFn: listCaseQueues });

  function updateFilter(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("page", "1");
    setParams(next);
  }

  async function handleBulkUpdate(status: string) {
    await bulkUpdateCases({ case_ids: selected, status });
    setSelected([]);
    queryClient.invalidateQueries({ queryKey: ["cases"] });
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await importCasesCsv(file);
      setImportMessage(`Imported ${result.created} case(s).${result.errors.length ? ` ${result.errors.length} row error(s).` : ""}`);
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    } catch (err) {
      setImportMessage(apiErrorMessage(err));
    }
    e.target.value = "";
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Cases</h1>
          <p>Operational case queues with SLA timers, escalation, comments, and evidence.</p>
        </div>
        <div className="page-header-actions">
          <label className="btn btn-sm">
            Import CSV
            <input type="file" accept=".csv" hidden onChange={handleImport} />
          </label>
          <button className="btn btn-sm" onClick={() => downloadCasesCsv()}>
            Export CSV
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowNewCase(true)}>
            New case
          </button>
        </div>
      </div>

      {importMessage ? (
        <div className="disclaimer-banner" style={{ background: "#e9eefe", color: "#2454ff" }}>
          {importMessage}
        </div>
      ) : null}

      {showNewCase && queuesQuery.data ? (
        <NewCaseForm
          queues={queuesQuery.data}
          onClose={() => setShowNewCase(false)}
          onCreated={(id) => {
            setShowNewCase(false);
            navigate(`/cases/${id}`);
          }}
        />
      ) : null}

      <div className="filter-bar">
        <input
          placeholder="Search title…"
          defaultValue={filters.q}
          onKeyDown={(e) => {
            if (e.key === "Enter") updateFilter("q", (e.target as HTMLInputElement).value || null);
          }}
        />
        <select value={filters.status ?? ""} onChange={(e) => updateFilter("status", e.target.value || null)}>
          <option value="">All statuses</option>
          {["open", "in_progress", "pending_review", "escalated", "resolved", "closed"].map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <select
          value={filters.priority ?? ""}
          onChange={(e) => updateFilter("priority", e.target.value || null)}
        >
          <option value="">All priorities</option>
          {["low", "medium", "high", "critical"].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={!!filters.overdue_only}
            onChange={(e) => updateFilter("overdue_only", e.target.checked ? "true" : null)}
          />
          Overdue only
        </label>
        {selected.length > 0 ? (
          <span style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            {selected.length} selected
            <button className="btn btn-sm" onClick={() => handleBulkUpdate("in_progress")}>
              Mark in progress
            </button>
            <button className="btn btn-sm" onClick={() => handleBulkUpdate("closed")}>
              Close
            </button>
          </span>
        ) : null}
      </div>

      <div className="card" style={{ padding: 0 }}>
        {casesQuery.isLoading ? (
          <div className="loading-block">Loading cases…</div>
        ) : casesQuery.data && casesQuery.data.items.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Title</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Due</th>
                <th>SLA</th>
                <th>Escalation</th>
              </tr>
            </thead>
            <tbody>
              {casesQuery.data.items.map((c) => (
                <tr key={c.id} className="clickable">
                  <td onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.includes(c.id)}
                      onChange={(e) =>
                        setSelected((prev) =>
                          e.target.checked ? [...prev, c.id] : prev.filter((id) => id !== c.id),
                        )
                      }
                    />
                  </td>
                  <td onClick={() => navigate(`/cases/${c.id}`)}>
                    #{c.id} {c.title}
                  </td>
                  <td onClick={() => navigate(`/cases/${c.id}`)}>
                    <StatusBadge value={c.status} />
                  </td>
                  <td onClick={() => navigate(`/cases/${c.id}`)}>
                    <StatusBadge value={c.priority} />
                  </td>
                  <td onClick={() => navigate(`/cases/${c.id}`)}>
                    {c.due_at ? new Date(c.due_at).toLocaleDateString() : "—"}
                  </td>
                  <td onClick={() => navigate(`/cases/${c.id}`)}>
                    {c.sla_breached ? <StatusBadge value="failed" /> : <StatusBadge value="acknowledged" />}
                  </td>
                  <td onClick={() => navigate(`/cases/${c.id}`)}>{c.escalation_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No cases match these filters.</div>
        )}
      </div>

      {casesQuery.data ? (
        <div className="pagination">
          <span>
            Page {casesQuery.data.page} — {casesQuery.data.total} total
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
            disabled={page * 20 >= casesQuery.data.total}
            onClick={() => updateFilter("page", String(page + 1))}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}

function NewCaseForm({
  queues,
  onClose,
  onCreated,
}: {
  queues: { id: number; name: string }[];
  onClose: () => void;
  onCreated: (id: number) => void;
}) {
  const [title, setTitle] = useState("");
  const [queueId, setQueueId] = useState(queues[0]?.id ?? 0);
  const [priority, setPriority] = useState("medium");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const created = await createCase({ queue_id: queueId, title, priority });
      onCreated(created.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <div className="card">
      <div className="section-title">New case</div>
      {error ? <div className="login-error">{error}</div> : null}
      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-3">
          <div className="form-row">
            <label htmlFor="new-case-title">Title</label>
            <input
              id="new-case-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="new-case-queue">Queue</label>
            <select
              id="new-case-queue"
              value={queueId}
              onChange={(e) => setQueueId(Number(e.target.value))}
            >
              {queues.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="new-case-priority">Priority</label>
            <select
              id="new-case-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
            >
              {["low", "medium", "high", "critical"].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
        </div>
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
