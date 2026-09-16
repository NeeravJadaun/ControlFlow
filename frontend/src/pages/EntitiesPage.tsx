import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { downloadEntitiesCsv, importEntitiesCsv, listEntities } from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function EntitiesPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const page = Number(params.get("page") ?? "1");

  const filters = {
    kind: params.get("kind") ?? undefined,
    q: params.get("q") ?? undefined,
    page,
  };
  const entitiesQuery = useQuery({ queryKey: ["entities", filters], queryFn: () => listEntities(filters) });

  function updateFilter(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("page", "1");
    setParams(next);
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await importEntitiesCsv(file);
      setImportMessage(
        `Imported ${result.created} entity(ies).${result.errors.length ? ` ${result.errors.length} row error(s).` : ""}`,
      );
      queryClient.invalidateQueries({ queryKey: ["entities"] });
    } catch (err) {
      setImportMessage(apiErrorMessage(err));
    }
    e.target.value = "";
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Entities &amp; Accounts</h1>
          <p>Dealers, clients, and onboarding records with linked accounts and contacts.</p>
        </div>
        <div className="page-header-actions">
          <label className="btn btn-sm">
            Import CSV
            <input type="file" accept=".csv" hidden onChange={handleImport} />
          </label>
          <button className="btn btn-sm" onClick={() => downloadEntitiesCsv()}>
            Export CSV
          </button>
        </div>
      </div>

      {importMessage ? (
        <div className="disclaimer-banner" style={{ background: "#e9eefe", color: "#2454ff" }}>
          {importMessage}
        </div>
      ) : null}

      <div className="filter-bar">
        <input
          placeholder="Search name…"
          defaultValue={filters.q}
          onKeyDown={(e) => {
            if (e.key === "Enter") updateFilter("q", (e.target as HTMLInputElement).value || null);
          }}
        />
        <select value={filters.kind ?? ""} onChange={(e) => updateFilter("kind", e.target.value || null)}>
          <option value="">All kinds</option>
          <option value="dealer">Dealer</option>
          <option value="client">Client</option>
          <option value="onboarding_record">Onboarding record</option>
        </select>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {entitiesQuery.isLoading ? (
          <div className="loading-block">Loading entities…</div>
        ) : entitiesQuery.data && entitiesQuery.data.items.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Kind</th>
                <th>Status</th>
                <th>Jurisdiction</th>
              </tr>
            </thead>
            <tbody>
              {entitiesQuery.data.items.map((e) => (
                <tr key={e.id} className="clickable" onClick={() => navigate(`/entities/${e.id}`)}>
                  <td>#{e.id}</td>
                  <td>{e.name}</td>
                  <td>
                    <StatusBadge value={e.kind} />
                  </td>
                  <td>{e.status}</td>
                  <td>{e.jurisdiction ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No entities match these filters.</div>
        )}
      </div>

      {entitiesQuery.data ? (
        <div className="pagination">
          <span>
            Page {entitiesQuery.data.page} — {entitiesQuery.data.total} total
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
            disabled={page * 25 >= entitiesQuery.data.total}
            onClick={() => updateFilter("page", String(page + 1))}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}
