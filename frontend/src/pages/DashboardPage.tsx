import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getDashboardSummary, getMonthlyTrend, getSlaTrend } from "../api/endpoints";
import { StatTile } from "../components/StatTile";

const COLORS = {
  primary: "#2454ff",
  success: "#1a8a5f",
  warning: "#b3720b",
  danger: "#c8332a",
  grid: "#eef0f3",
};

export function DashboardPage() {
  const summaryQuery = useQuery({ queryKey: ["dashboard-summary"], queryFn: getDashboardSummary });
  const slaTrendQuery = useQuery({ queryKey: ["sla-trend"], queryFn: () => getSlaTrend(90) });
  const monthlyTrendQuery = useQuery({ queryKey: ["monthly-trend"], queryFn: () => getMonthlyTrend(6) });

  if (summaryQuery.isLoading) return <div className="loading-block">Loading dashboard…</div>;
  if (summaryQuery.isError || !summaryQuery.data) {
    return <div className="loading-block">Could not load dashboard metrics.</div>;
  }

  const s = summaryQuery.data;
  const remediationOpen = (s.remediation.open ?? 0) + (s.remediation.in_progress ?? 0);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Operations Dashboard</h1>
          <p>
            Live open/overdue cases, SLA attainment, document renewal status, and control testing
            health — every tile drills down into the underlying record list.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-4">
        <StatTile label="Open cases" value={s.cases.open} to="/cases?open_only=true" />
        <StatTile
          label="Overdue cases"
          value={s.cases.overdue}
          sub={`${s.cases.open ? Math.round((s.cases.overdue / s.cases.open) * 100) : 0}% of open`}
          to="/cases?overdue_only=true"
        />
        <StatTile
          label="SLA attainment"
          value={`${s.sla.attainment_rate}%`}
          sub={`${s.sla.resolved_within_sla}/${s.sla.total_resolved} resolved on time`}
          to="/cases?status=resolved"
        />
        <StatTile
          label="Documents expiring (90d)"
          value={s.documents.expiring_within_window}
          sub={`${s.documents.expired} already expired`}
          to="/documents?expiring_within_days=90"
        />
        <StatTile
          label="Control pass rate"
          value={`${s.controls.pass_rate}%`}
          sub={`${s.controls.passed}/${s.controls.total_tests} tests passed`}
          to="/controls"
        />
        <StatTile label="Open remediation tasks" value={remediationOpen} to="/controls?tab=remediation" />
        <StatTile
          label="Critical priority cases"
          value={s.cases.by_priority.critical ?? 0}
          to="/cases?priority=critical&open_only=true"
        />
        <StatTile
          label="Exceptions aged 60+ days"
          value={s.exception_aging["60_plus"] ?? 0}
          to="/controls?tab=remediation"
        />
      </div>

      <div className="two-col" style={{ marginTop: 20 }}>
        <div className="card">
          <div className="section-title">SLA attainment trend (90 days)</div>
          {slaTrendQuery.data && slaTrendQuery.data.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={slaTrendQuery.data}>
                <CartesianGrid stroke={COLORS.grid} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
                <YAxis tick={{ fontSize: 11 }} width={36} domain={[0, 100]} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Line
                  type="monotone"
                  dataKey="attainment_rate"
                  stroke={COLORS.primary}
                  strokeWidth={2}
                  dot={false}
                  name="Attainment %"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">No resolved cases in this window yet.</div>
          )}
        </div>

        <div className="card">
          <div className="section-title">Workload by owner</div>
          {s.workload.length === 0 ? (
            <div className="empty-state">No assigned open cases.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Owner</th>
                  <th>Open cases</th>
                </tr>
              </thead>
              <tbody>
                {s.workload.map((w) => (
                  <tr key={w.owner_id}>
                    <td>{w.owner_name}</td>
                    <td>{w.open_cases}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="section-title">Case volume — created vs. resolved (6 months)</div>
        {monthlyTrendQuery.data && monthlyTrendQuery.data.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={monthlyTrendQuery.data}>
              <CartesianGrid stroke={COLORS.grid} vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={30} />
              <Tooltip />
              <Bar dataKey="created" fill={COLORS.primary} name="Created" radius={[4, 4, 0, 0]} />
              <Bar dataKey="resolved" fill={COLORS.success} name="Resolved" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">Not enough history yet.</div>
        )}
      </div>

      <div className="grid grid-cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="section-title">Control pass rate by control</div>
          <table>
            <thead>
              <tr>
                <th>Control</th>
                <th>Tests</th>
                <th>Pass rate</th>
              </tr>
            </thead>
            <tbody>
              {s.controls.by_control.slice(0, 8).map((c) => (
                <tr key={c.key}>
                  <td>{c.name}</td>
                  <td>{c.total}</td>
                  <td>{c.pass_rate}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="section-title">Exception aging</div>
          <table>
            <thead>
              <tr>
                <th>Age bucket</th>
                <th>Open exceptions</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>0–7 days</td>
                <td>{s.exception_aging["0_7"] ?? 0}</td>
              </tr>
              <tr>
                <td>8–30 days</td>
                <td>{s.exception_aging["8_30"] ?? 0}</td>
              </tr>
              <tr>
                <td>31–60 days</td>
                <td>{s.exception_aging["31_60"] ?? 0}</td>
              </tr>
              <tr>
                <td>60+ days</td>
                <td>{s.exception_aging["60_plus"] ?? 0}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
