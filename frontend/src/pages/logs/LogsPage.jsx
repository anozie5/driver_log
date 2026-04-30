import { useState, useEffect } from "react";
import * as API from "../../api/client.js";
import { fmtDate, fmtTime, fmtHours, errorMsg } from "../../hooks/utils.js";
import { Icon } from "../../components/Icons.jsx";
import Modal from "../../components/Modal.jsx";
import ActivityGrid from "../../components/ActivityGrid.jsx";

// ─── Module-level fetch helpers ───────────────────────────────
// Defined outside the component so they never appear in any
// closure, eliminating every exhaustive-deps warning entirely.
function fetchLogs(period, setLogs, setLoading) {
  setLoading(true);
  API.getLogs({ period })
    .then(res => setLogs(res || []))
    .catch(() => {})
    .finally(() => setLoading(false));
}

async function fetchLog(id, setSelectedLog) {
  const log = await API.getLog(id);
  setSelectedLog(log);
}

// ─────────────────────────────────────────────────────────────
// LogsPage
// ─────────────────────────────────────────────────────────────
export default function LogsPage({ user }) {
  const [period, setPeriod]             = useState("this_week");
  const [logs, setLogs]                 = useState([]);
  const [loading, setLoading]           = useState(false);
  const [selectedLog, setSelectedLog]   = useState(null);
  const [showCreate, setShowCreate]     = useState(false);
  const [showActModal, setShowActModal] = useState(null);

  useEffect(() => {
    fetchLogs(period, setLogs, setLoading);
  }, [period]);

  function load() { fetchLogs(period, setLogs, setLoading); }
  function openLog(id) { fetchLog(id, setSelectedLog); }

  const totalMiles    = logs.reduce((s,l) => s + parseFloat(l.total_miles_driven||0), 0);
  const totalDriving  = logs.reduce((s,l) => s + parseFloat(l.total_hours_driving||0), 0);
  const totalOnDuty   = logs.reduce((s,l) => s + parseFloat(l.total_hours_on_duty||0), 0);

  return (
    <div className="page">
      {/* Period filter bar */}
      <div className="period-bar">
        {[["today","Today"],["this_week","This Week"],["this_month","This Month"],["this_year","This Year"]].map(([v,l]) => (
          <button key={v} className={`period-btn${period===v?" active":""}`} onClick={() => setPeriod(v)}>{l}</button>
        ))}
        <button className="btn btn-primary btn-sm" style={{ marginLeft: "auto" }} onClick={() => setShowCreate(true)}>
          <Icon.Plus /> New Log
        </button>
      </div>

      {/* Stats */}
      <div className="stat-row">
        {[
          ["Total Logs",    logs.length,            ""],
          ["Miles Driven",  totalMiles.toFixed(0),  "miles"],
          ["Driving Hours", totalDriving.toFixed(1),"hours"],
          ["On Duty Hours", totalOnDuty.toFixed(1), "hours"],
        ].map(([label, value, unit]) => (
          <div key={label} className="stat-card">
            <div className="stat-label">{label}</div>
            <div className="stat-value">{value}</div>
            {unit && <div className="stat-unit">{unit}</div>}
          </div>
        ))}
      </div>

      {/* Logs table */}
      <div className="card">
        <div className="card-head">
          <span className="card-head-title">Daily Logs</span>
          {loading && <span className="spin" />}
        </div>
        <div className="table-wrap">
          {logs.length === 0 && !loading
            ? <div className="empty"><div className="empty-icon">📋</div><p>No logs for this period</p></div>
            : (
              <table>
                <thead>
                  <tr>
                    <th>Date</th><th>From → To</th><th>Vehicle</th>
                    <th>Miles</th><th>Driving</th><th>On Duty</th>
                    <th>Co-Driver</th><th>Status</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id}>
                      <td className="mono">{fmtDate(log.day)}</td>
                      <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {log.from_location} → {log.to_location}
                      </td>
                      <td className="mono">{log.vehicle_number || "—"}</td>
                      <td className="mono">{parseFloat(log.total_miles_driven||0).toFixed(1)}</td>
                      <td className="mono">{fmtHours(log.total_hours_driving)}</td>
                      <td className="mono">{fmtHours(log.total_hours_on_duty)}</td>
                      <td>
                        {log.co_driver_email
                          ? <span style={{ fontSize: 12 }}>{log.co_driver_email}</span>
                          : log.is_co_driver_entry
                            ? <span className="badge badge-blue">Co-Driver</span>
                            : "—"}
                      </td>
                      <td><ApprovalBadge status={log.co_driver_approval_status} /></td>
                      <td>
                        <button className="btn btn-ghost btn-sm" onClick={() => openLog(log.id)}>View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </div>
      </div>

      {/* Modals */}
      {selectedLog && (
        <LogDetailModal
          log={selectedLog}
          user={user}
          onClose={() => setSelectedLog(null)}
          onAddAct={() => setShowActModal(selectedLog.id)}
          onRefresh={() => { openLog(selectedLog.id); load(); }}
        />
      )}
      {showCreate && (
        <CreateLogModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} />
      )}
      {showActModal && (
        <AddActModal
          logId={showActModal}
          onClose={() => setShowActModal(null)}
          onCreated={() => { setShowActModal(null); if (selectedLog) openLog(selectedLog.id); }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Shared badge helper (also used by ManagerPage)
// ─────────────────────────────────────────────────────────────
export function ApprovalBadge({ status }) {
  if (status === "pending")  return <span className="badge badge-amber">Pending</span>;
  if (status === "approved") return <span className="badge badge-green">Approved</span>;
  if (status === "rejected") return <span className="badge badge-red">Rejected</span>;
  return <span className="badge badge-blue">Active</span>;
}

// ─────────────────────────────────────────────────────────────
// LogDetailModal — full log view with 24-hr grid + activity list
// ─────────────────────────────────────────────────────────────
export function LogDetailModal({ log, onClose, onAddAct, onRefresh }) {
  const [submitting, setSubmitting]   = useState(false);
  const [primaryLogId, setPrimaryLogId] = useState("");

  const actColors = { D: "driving", ON: "on-duty", OF: "off-duty", SB: "sleeping" };

  async function deleteLog() {
    if (!confirm("Delete this log and all its activities?")) return;
    await API.deleteLog(log.id);
    onRefresh(); onClose();
  }

  async function submitCo() {
    setSubmitting(true);
    try {
      await API.submitCoDriver(log.id, parseInt(primaryLogId));
      onRefresh(); onClose();
    } catch (e) { alert(errorMsg(e)); }
    finally { setSubmitting(false); }
  }

  return (
    <Modal
      title={`Log — ${fmtDate(log.day)}`}
      onClose={onClose}
      footer={
        <div style={{ display: "flex", gap: 8, width: "100%", justifyContent: "space-between" }}>
          <button className="btn btn-danger btn-sm" onClick={deleteLog}>Delete Log</button>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={onAddAct}>+ Add Activity</button>
            <button className="btn btn-ghost btn-sm" onClick={onClose}>Close</button>
          </div>
        </div>
      }
    >
      {/* Header info grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        {[
          ["From",         log.from_location],
          ["To",           log.to_location],
          ["Vehicle",      log.vehicle_number || "—"],
          ["Miles Driven", parseFloat(log.total_miles_driven||0).toFixed(1)],
          ["Driving Hours",fmtHours(log.total_hours_driving)],
          ["On Duty Hours",fmtHours(log.total_hours_on_duty)],
          ["Off Duty",     fmtHours(log.total_hours_off_duty)],
          ["Sleeper",      fmtHours(log.total_hours_sleeping)],
        ].map(([k, v]) => (
          <div key={k}>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text3)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 2 }}>{k}</div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--text)" }}>{v}</div>
          </div>
        ))}
      </div>

      {/* 24-hour activity grid */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text3)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>
          24-Hour Activity Grid
        </div>
        <ActivityGrid actLogs={log.act_logs} day={log.day} />
      </div>

      {/* Activity table */}
      {log.act_logs?.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text3)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>
            Activities
          </div>
          <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Type","Start","End","Duration","Location"].map(h => (
                  <th key={h} style={{ fontFamily: "var(--mono)", fontWeight: 400, color: "var(--text3)", textAlign: "left", padding: "6px 8px", fontSize: 10 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {log.act_logs.map(act => (
                <tr key={act.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 8px 8px 0" }}>
                    <span className="badge" style={{
                      background: `rgba(var(--${actColors[act.activity] || "amber"}), .15)`,
                      color: `var(--${actColors[act.activity] || "amber"})`,
                    }}>
                      {act.activity_display || act.activity}
                    </span>
                  </td>
                  <td style={{ fontFamily: "var(--mono)", fontSize: 12, padding: "8px" }}>{fmtTime(act.start_time)}</td>
                  <td style={{ fontFamily: "var(--mono)", fontSize: 12, padding: "8px" }}>{fmtTime(act.end_time)}</td>
                  <td style={{ fontFamily: "var(--mono)", fontSize: 12, padding: "8px" }}>{fmtHours(act.duration_hours)}</td>
                  <td style={{ fontSize: 12, padding: "8px", color: "var(--text3)" }}>{act.location || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Co-driver submit section */}
      {!log.is_co_driver_entry && (
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 16 }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text3)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>
            Submit as Co-Driver
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              className="form-input"
              placeholder="Main driver's log ID"
              value={primaryLogId}
              onChange={e => setPrimaryLogId(e.target.value)}
              style={{ flex: 1 }}
            />
            <button className="btn btn-ghost btn-sm" onClick={submitCo}
              disabled={submitting || !primaryLogId}>
              {submitting ? <span className="spin" /> : "Submit"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────
// CreateLogModal
// ─────────────────────────────────────────────────────────────
export function CreateLogModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ day: new Date().toISOString().split("T")[0] });
  const [err, setErr]   = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function submit() {
    setErr(""); setLoading(true);
    try { await API.createLog(form); onCreated(); }
    catch (e) { setErr(errorMsg(e)); }
    finally { setLoading(false); }
  }

  return (
    <Modal title="New Daily Log" onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={submit} disabled={loading}>
          {loading ? <span className="spin" /> : "Create Log"}
        </button>
      </>}>
      {err && <div className="alert alert-err">{err}</div>}
      <div className="form-group">
        <label className="form-label">Date</label>
        <input type="date" className="form-input" value={form.day||""} onChange={e=>set("day",e.target.value)} />
      </div>
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">From Location</label>
          <input className="form-input" value={form.from_location||""} onChange={e=>set("from_location",e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">To Location</label>
          <input className="form-input" value={form.to_location||""} onChange={e=>set("to_location",e.target.value)} />
        </div>
      </div>
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Vehicle #</label>
          <input className="form-input" value={form.vehicle_number||""} onChange={e=>set("vehicle_number",e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Carrier</label>
          <input className="form-input" value={form.carrier_name||""} onChange={e=>set("carrier_name",e.target.value)} />
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">Remarks</label>
        <input className="form-input" value={form.remarks||""} onChange={e=>set("remarks",e.target.value)} />
      </div>
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────
// AddActModal
// ─────────────────────────────────────────────────────────────
export function AddActModal({ logId, onClose, onCreated }) {
  const today = new Date().toISOString().split("T")[0];
  const [form, setForm] = useState({ activity: "D", start_time: `${today}T08:00:00Z`, end_time: `${today}T10:00:00Z` });
  const [err, setErr]   = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function submit() {
    setErr(""); setLoading(true);
    try { await API.createAct(logId, { ...form, day_log: logId }); onCreated(); }
    catch (e) { setErr(errorMsg(e)); }
    finally { setLoading(false); }
  }

  return (
    <Modal title="Add Activity" onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={submit} disabled={loading}>
          {loading ? <span className="spin" /> : "Add Activity"}
        </button>
      </>}>
      {err && <div className="alert alert-err">{err}</div>}
      <div className="form-group">
        <label className="form-label">Activity Type</label>
        <select className="form-input form-select" value={form.activity} onChange={e=>set("activity",e.target.value)}>
          <option value="D">Driving</option>
          <option value="ON">On Duty (Not Driving)</option>
          <option value="OF">Off Duty</option>
          <option value="SB">Sleeper Berth</option>
        </select>
      </div>
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Start Time</label>
          <input type="datetime-local" className="form-input"
            value={form.start_time?.slice(0,16)||""}
            onChange={e => set("start_time", e.target.value+":00Z")} />
        </div>
        <div className="form-group">
          <label className="form-label">End Time</label>
          <input type="datetime-local" className="form-input"
            value={form.end_time?.slice(0,16)||""}
            onChange={e => set("end_time", e.target.value+":00Z")} />
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">Location</label>
        <input className="form-input" value={form.location||""} onChange={e=>set("location",e.target.value)} />
      </div>
      <div className="form-group">
        <label className="form-label">Remarks</label>
        <input className="form-input" value={form.remarks||""} onChange={e=>set("remarks",e.target.value)} />
      </div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text3)", marginTop: -8 }}>
        Times must be on 15-minute boundaries (:00, :15, :30, :45)
      </div>
    </Modal>
  );
}