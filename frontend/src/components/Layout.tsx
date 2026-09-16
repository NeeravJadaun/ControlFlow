import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/cases", label: "Cases" },
  { to: "/documents", label: "Documents" },
  { to: "/entities", label: "Entities & Accounts" },
  { to: "/controls", label: "Controls & Testing" },
  { to: "/financial", label: "Financial Ops Workspace" },
  { to: "/audit", label: "Audit Log" },
];

const ROLE_LABELS: Record<string, string> = {
  operations_analyst: "Operations Analyst",
  reviewer: "Reviewer",
  compliance_officer: "Compliance Officer",
  auditor: "Auditor",
  admin: "Admin",
};

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          Control<span>Flow</span>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <strong>{user?.full_name}</strong>
          {user ? ROLE_LABELS[user.role] ?? user.role : null}
          <br />
          <button onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
