import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiClient } from "../api/client";
import { getEntity, listDocuments } from "../api/endpoints";
import { StatusBadge } from "../components/StatusBadge";
import type { Account, Contact } from "../types";

async function listAccountsForEntity(entityId: number): Promise<Account[]> {
  const { data } = await apiClient.get(`/api/entities/${entityId}/accounts`);
  return data;
}

async function listContactsForEntity(entityId: number): Promise<Contact[]> {
  const { data } = await apiClient.get(`/api/entities/${entityId}/contacts`);
  return data;
}

export function EntityDetailPage() {
  const { id } = useParams();
  const entityId = Number(id);
  const navigate = useNavigate();

  const entityQuery = useQuery({ queryKey: ["entity", entityId], queryFn: () => getEntity(entityId) });
  const accountsQuery = useQuery({
    queryKey: ["entity-accounts", entityId],
    queryFn: () => listAccountsForEntity(entityId),
  });
  const contactsQuery = useQuery({
    queryKey: ["entity-contacts", entityId],
    queryFn: () => listContactsForEntity(entityId),
  });
  const documentsQuery = useQuery({
    queryKey: ["entity-documents", entityId],
    queryFn: () => listDocuments({ entity_id: entityId, page_size: 50 }),
  });

  if (entityQuery.isLoading) return <div className="loading-block">Loading entity…</div>;
  if (!entityQuery.data) return <div className="loading-block">Entity not found.</div>;
  const e = entityQuery.data;

  return (
    <div>
      <div className="breadcrumb">
        <Link to="/entities">← Back to entities</Link>
      </div>
      <div className="page-header">
        <div>
          <h1>{e.name}</h1>
          <p>
            <StatusBadge value={e.kind} /> &nbsp; {e.status} &nbsp; {e.jurisdiction}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2">
        <div className="card">
          <div className="section-title">Accounts</div>
          {accountsQuery.data && accountsQuery.data.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Account #</th>
                  <th>Type</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {accountsQuery.data.map((a) => (
                  <tr key={a.id}>
                    <td>{a.account_number}</td>
                    <td>{a.account_type}</td>
                    <td>{a.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">No accounts.</div>
          )}
        </div>
        <div className="card">
          <div className="section-title">Contacts</div>
          {contactsQuery.data && contactsQuery.data.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Email</th>
                </tr>
              </thead>
              <tbody>
                {contactsQuery.data.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td>{c.role ?? "—"}</td>
                    <td>{c.email ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">No contacts.</div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="section-title">Documents</div>
        {documentsQuery.data && documentsQuery.data.items.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Completeness</th>
                <th>Expiry</th>
              </tr>
            </thead>
            <tbody>
              {documentsQuery.data.items.map((d) => (
                <tr key={d.id} className="clickable" onClick={() => navigate(`/documents/${d.id}`)}>
                  <td>#{d.id}</td>
                  <td>
                    <StatusBadge value={d.review_status} />
                  </td>
                  <td>{d.completeness_score}%</td>
                  <td>{d.expiry_date ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No documents on file.</div>
        )}
      </div>
    </div>
  );
}
