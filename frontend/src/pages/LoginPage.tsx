import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiErrorMessage } from "../api/client";

const DEMO_CREDENTIALS = [
  ["Admin", "admin@controlflow.demo", "Admin123!"],
  ["Compliance Officer", "compliance.officer@controlflow.demo", "Compliance123!"],
  ["Reviewer", "reviewer@controlflow.demo", "Reviewer123!"],
  ["Auditor", "auditor@controlflow.demo", "Auditor123!"],
  ["Operations Analyst", "analyst@controlflow.demo", "Analyst123!"],
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@controlflow.demo");
  const [password, setPassword] = useState("Admin123!");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>ControlFlow</h1>
        <p className="subtitle">Operations &amp; Compliance Management Platform</p>

        {error ? <div className="login-error">{error}</div> : null}

        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={submitting} style={{ width: "100%" }}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="demo-creds">
          Synthetic demo credentials (click a row to autofill):
          <table>
            <tbody>
              {DEMO_CREDENTIALS.map(([label, demoEmail, demoPassword]) => (
                <tr
                  key={demoEmail}
                  style={{ cursor: "pointer" }}
                  onClick={() => {
                    setEmail(demoEmail);
                    setPassword(demoPassword);
                  }}
                >
                  <td>{label}</td>
                  <td>{demoEmail}</td>
                  <td>{demoPassword}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
