import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  downloadEvidenceCsv,
  listControlTests,
  listControls,
  listRemediationTasks,
  recordControlTest,
  signOffControlTest,
  updateRemediationTask,
} from "../api/endpoints";
import { apiErrorMessage } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../auth/AuthContext";

const TESTER_ROLES = ["reviewer", "compliance_officer", "auditor", "admin"];
const SIGNOFF_ROLES = ["compliance_officer", "auditor", "admin"];

export function ControlsPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "controls";
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedControlId, setSelectedControlId] = useState<number | null>(null);
  const [testDate, setTestDate] = useState(new Date().toISOString().slice(0, 10));
  const [result, setResult] = useState("pass");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const controlsQuery = useQuery({ queryKey: ["controls"], queryFn: listControls });
  const testsQuery = useQuery({
    queryKey: ["control-tests", selectedControlId],
    queryFn: () => listControlTests(selectedControlId!),
    enabled: !!selectedControlId,
  });
  const remediationQuery = useQuery({
    queryKey: ["remediation-tasks"],
    queryFn: () => listRemediationTasks(),
    enabled: tab === "remediation",
  });

  const canTest = user && TESTER_ROLES.includes(user.role);
  const canSignOff = user && SIGNOFF_ROLES.includes(user.role);

  const recordMutation = useMutation({
    mutationFn: () =>
      recordControlTest({ control_id: selectedControlId!, test_date: testDate, result, notes }),
    onSuccess: () => {
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["control-tests", selectedControlId] });
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  const signOffMutation = useMutation({
    mutationFn: (testId: number) => signOffControlTest(testId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["control-tests", selectedControlId] }),
    onError: (e) => setError(apiErrorMessage(e)),
  });

  const remediationMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => updateRemediationTask(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["remediation-tasks"] }),
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Controls &amp; Testing</h1>
          <p>Control library, sample-based testing, sign-off, and remediation tracking.</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-sm" onClick={() => downloadEvidenceCsv()}>
            Export audit evidence
          </button>
        </div>
      </div>

      <div className="tabs">
        <div
          className={`tab ${tab === "controls" ? "active" : ""}`}
          onClick={() => setParams({ tab: "controls" })}
        >
          Controls &amp; Tests
        </div>
        <div
          className={`tab ${tab === "remediation" ? "active" : ""}`}
          onClick={() => setParams({ tab: "remediation" })}
        >
          Remediation Tasks
        </div>
      </div>

      {error ? <div className="login-error">{error}</div> : null}

      {tab === "controls" ? (
        <div className="two-col">
          <div className="card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>Control</th>
                  <th>Frequency</th>
                </tr>
              </thead>
              <tbody>
                {controlsQuery.data?.map((c) => (
                  <tr
                    key={c.id}
                    className="clickable"
                    onClick={() => setSelectedControlId(c.id)}
                    style={{ background: selectedControlId === c.id ? "#f4f6ff" : undefined }}
                  >
                    <td>{c.name}</td>
                    <td>
                      <StatusBadge value={c.frequency} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            {selectedControlId ? (
              <>
                {canTest ? (
                  <div className="card">
                    <div className="section-title">Record control test</div>
                    <div className="form-row">
                      <label htmlFor="control-test-date">Test date</label>
                      <input
                        id="control-test-date"
                        type="date"
                        value={testDate}
                        onChange={(e) => setTestDate(e.target.value)}
                      />
                    </div>
                    <div className="form-row">
                      <label htmlFor="control-test-result">Result</label>
                      <select
                        id="control-test-result"
                        value={result}
                        onChange={(e) => setResult(e.target.value)}
                      >
                        <option value="pass">Pass</option>
                        <option value="fail">Fail</option>
                      </select>
                    </div>
                    <div className="form-row">
                      <label htmlFor="control-test-notes">Notes</label>
                      <textarea
                        id="control-test-notes"
                        rows={2}
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                      />
                    </div>
                    <button className="btn btn-primary" onClick={() => recordMutation.mutate()}>
                      Record test
                    </button>
                  </div>
                ) : null}

                <div className="card">
                  <div className="section-title">Test history</div>
                  {testsQuery.data && testsQuery.data.length > 0 ? (
                    <table>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Result</th>
                          <th>Notes</th>
                          <th>Signed off</th>
                        </tr>
                      </thead>
                      <tbody>
                        {testsQuery.data.map((t) => (
                          <tr key={t.id}>
                            <td>{t.test_date}</td>
                            <td>
                              <StatusBadge value={t.result} />
                            </td>
                            <td>{t.notes ?? "—"}</td>
                            <td>
                              {t.signed_off_at ? (
                                "Yes"
                              ) : canSignOff ? (
                                <button className="btn btn-sm" onClick={() => signOffMutation.mutate(t.id)}>
                                  Sign off
                                </button>
                              ) : (
                                "No"
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="empty-state">No tests recorded yet.</div>
                  )}
                </div>
              </>
            ) : (
              <div className="card empty-state">Select a control to view test history.</div>
            )}
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          {remediationQuery.data && remediationQuery.data.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Description</th>
                  <th>Due date</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {remediationQuery.data.map((task) => (
                  <tr key={task.id}>
                    <td>{task.description}</td>
                    <td>{task.due_date ?? "—"}</td>
                    <td>
                      <StatusBadge value={task.status} />
                    </td>
                    <td>
                      {task.status !== "resolved" && (
                        <button
                          className="btn btn-sm"
                          onClick={() => remediationMutation.mutate({ id: task.id, status: "resolved" })}
                        >
                          Mark resolved
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">No remediation tasks.</div>
          )}
        </div>
      )}
    </div>
  );
}
