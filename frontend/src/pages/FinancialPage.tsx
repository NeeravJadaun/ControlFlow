import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  acknowledgeDistribution,
  listClassifications,
  listDistributions,
  markDistributionSent,
} from "../api/endpoints";
import { StatusBadge } from "../components/StatusBadge";

export function FinancialPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "classifications";
  const queryClient = useQueryClient();

  const classificationsQuery = useQuery({
    queryKey: ["classifications"],
    queryFn: () => listClassifications({ page_size: 50 }),
    enabled: tab === "classifications",
  });
  const distributionsQuery = useQuery({
    queryKey: ["distributions"],
    queryFn: () => listDistributions({ page_size: 50 }),
    enabled: tab === "distributions",
  });

  const sentMutation = useMutation({
    mutationFn: (id: number) => markDistributionSent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["distributions"] }),
  });
  const ackMutation = useMutation({
    mutationFn: (id: number) => acknowledgeDistribution(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["distributions"] }),
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Financial Operations Workspace</h1>
          <p>Synthetic tax-document and regulatory monitoring demo built on the core platform.</p>
        </div>
      </div>

      <div className="disclaimer-banner">
        Educational and simplified only. These classification rules and monitoring statuses are
        not legal, tax, or regulatory advice, and must never be used for real compliance decisions.
      </div>

      <div className="tabs">
        <div
          className={`tab ${tab === "classifications" ? "active" : ""}`}
          onClick={() => setParams({ tab: "classifications" })}
        >
          FATCA / CRS / QI Classifications
        </div>
        <div
          className={`tab ${tab === "distributions" ? "active" : ""}`}
          onClick={() => setParams({ tab: "distributions" })}
        >
          Fund Fact Sheets &amp; Maturity Notices
        </div>
      </div>

      {tab === "classifications" ? (
        <div className="card" style={{ padding: 0 }}>
          {classificationsQuery.data && classificationsQuery.data.items.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Regime</th>
                  <th>Classification</th>
                  <th>Status</th>
                  <th>Review due</th>
                </tr>
              </thead>
              <tbody>
                {classificationsQuery.data.items.map((c) => (
                  <tr key={c.id}>
                    <td>#{c.entity_id}</td>
                    <td>{c.regime}</td>
                    <td>{c.classification_value ?? "—"}</td>
                    <td>
                      <StatusBadge value={c.status} />
                    </td>
                    <td>{c.review_due_date ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">No classifications recorded.</div>
          )}
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          {distributionsQuery.data && distributionsQuery.data.items.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Kind</th>
                  <th>Reference</th>
                  <th>Entity</th>
                  <th>Effective date</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {distributionsQuery.data.items.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <StatusBadge value={d.kind} />
                    </td>
                    <td>{d.reference_name}</td>
                    <td>#{d.entity_id}</td>
                    <td>{d.effective_date}</td>
                    <td>
                      <StatusBadge value={d.status} />
                    </td>
                    <td>
                      {d.status === "pending" && (
                        <button className="btn btn-sm" onClick={() => sentMutation.mutate(d.id)}>
                          Mark sent
                        </button>
                      )}
                      {d.status === "sent" && (
                        <button className="btn btn-sm" onClick={() => ackMutation.mutate(d.id)}>
                          Acknowledge
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">No distributions recorded.</div>
          )}
        </div>
      )}
    </div>
  );
}
