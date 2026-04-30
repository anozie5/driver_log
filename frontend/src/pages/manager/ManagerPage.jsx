import { useState, useEffect } from "react";
import * as API from "../../api/client.js";
import { fmtDate, fmtHours } from "../../hooks/utils.js";
import { LogDetailModal } from "../logs/LogsPage.jsx";

// ─── Module-level fetch helpers ───────────────────────────────
function fetchDrivers(setDrivers) {
  API.getDrivers().then(setDrivers).catch(() => {});
}

function fetchDriverLogs(selectedId, period, setDriverLogs, setLoading) {
  setLoading(true);
  API.getDriverLogs(selectedId, { period })
    .then(setDriverLogs)
    .catch(() => setDriverLogs([]))
    .finally(() => setLoading(false));
}

// ─────────────────────────────────────────────────────────────
// ManagerPage
// ─────────────────────────────────────────────────────────────
export default function ManagerPage() {
  const [drivers, setDrivers]       = useState([]);
  const [selected, setSelected]     = useState(null);
  const [driverLogs, setDriverLogs] = useState([]);
  const [period, setPeriod]         = useState("this_week");
  const [loading, setLoading]       = useState(false);
  const [logDetail, setLogDetail]   = useState(null);

  useEffect(() => {
    fetchDrivers(setDrivers);
  }, []);

  useEffect(() => {
    if (!selected) return;
    fetchDriverLogs(selected.id, period, setDriverLogs, setLoading);
  }, [selected, period]);

  const totalMiles   = driverLogs.reduce((s,l) => s + parseFloat(l.total_miles_driven||0), 0);
  const totalDriving = driverLogs.reduce((s,l) => s + parseFloat(l.total_hours_driving||0), 0);
  const totalOnDuty  = driverLogs.reduce((s,l) => s + parseFloat(l.total_hours_on_duty||0), 0);

  return (
    <div className="page">
      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 20 }}>

        {/* Driver list */}
        <div className="card" style={{ height: "fit-content" }}>
          <div className="card-head">
            <span className="card-head-title">Drivers ({drivers.length})</span>
          </div>
          <div>
            {drivers.length === 0
              ? <div className="empty" style={{ padding: 24 }}><p>No drivers found</p></div>
              : drivers.map(d => (
                <div key={d.id} onClick={() => setSelected(d)} style={{
                  padding: "11px 18px", cursor: "pointer",
                  borderBottom: "1px solid var(--border)",
                  background: selected?.id === d.id ? "var(--bg3)" : "transparent",
                  borderLeft: `2px solid ${selected?.id === d.id ? "var(--amber)" : "transparent"}`,
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{d.name}</div>
                  <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text3)", marginTop: 2 }}>
                    {d.designation_number || d.email} · {d.total_logs} logs
                  </div>
                </div>
              ))}
          </div>
        </div>

        {/* Driver detail pane */}
        <div>
          {!selected ? (
            <div className="card">
              <div className="empty">
                <div className="empty-icon">👈</div>
                <p>Select a driver to view their logs</p>
              </div>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{selected.name}</div>
                  <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text3)" }}>{selected.email}</div>
                </div>
              </div>

              {/* Period filter */}
              <div className="period-bar">
                {[["today","Today"],["this_week","This Week"],["this_month","This Month"],["this_year","This Year"]].map(([v,l]) => (
                  <button key={v} className={`period-btn${period===v?" active":""}`} onClick={() => setPeriod(v)}>{l}</button>
                ))}
                {loading && <span className="spin" style={{ marginLeft: 8 }} />}
              </div>

              {/* Stats */}
              <div className="stat-row" style={{ marginBottom: 16 }}>
                {[
                  ["Logs",      driverLogs.length],
                  ["Miles",     totalMiles.toFixed(0)],
                  ["Drive Hrs", totalDriving.toFixed(1)],
                  ["On Duty",   totalOnDuty.toFixed(1)],
                ].map(([l,v]) => (
                  <div key={l} className="stat-card">
                    <div className="stat-label">{l}</div>
                    <div className="stat-value">{v}</div>
                  </div>
                ))}
              </div>

              {/* Logs table */}
              <div className="card">
                <div className="table-wrap">
                  {driverLogs.length === 0
                    ? <div className="empty"><p>No logs for this period</p></div>
                    : (
                      <table>
                        <thead>
                          <tr>
                            <th>Date</th><th>From → To</th><th>Miles</th>
                            <th>Driving</th><th>On Duty</th><th>Co-Driver</th><th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {driverLogs.map(log => (
                            <tr key={log.id}>
                              <td className="mono">{fmtDate(log.day)}</td>
                              <td style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {log.from_location} → {log.to_location}
                              </td>
                              <td className="mono">{parseFloat(log.total_miles_driven||0).toFixed(0)}</td>
                              <td className="mono">{fmtHours(log.total_hours_driving)}</td>
                              <td className="mono">{fmtHours(log.total_hours_on_duty)}</td>
                              <td>{log.co_driver_email || "—"}</td>
                              <td>
                                <button className="btn btn-ghost btn-sm" onClick={async () => {
                                  const full = await API.getLog(log.id);
                                  setLogDetail(full);
                                }}>View</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Log detail modal (read-only for managers) */}
      {logDetail && (
        <LogDetailModal
          log={logDetail}
          onClose={() => setLogDetail(null)}
          onAddAct={() => {}}
          onRefresh={() => {}}
        />
      )}
    </div>
  );
}