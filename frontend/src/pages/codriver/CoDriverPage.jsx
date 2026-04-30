import { useState, useEffect } from "react";
import * as API from "../../api/client.js";
import { fmtDate, fmtHours, errorMsg } from "../../hooks/utils.js";
import { Icon } from "../../components/Icons.jsx";

// ─── Module-level fetch helpers ───────────────────────────────
function fetchCoDriverData(setPending, setMyLogs, setLoading) {
  setLoading(true);
  Promise.all([
    API.getPendingCoDrivers().catch(() => []),
    API.getLogs({ period: "this_week" }).catch(() => []),
  ]).then(([p, l]) => {
    setPending(p || []);
    setMyLogs(l || []);
  }).finally(() => setLoading(false));
}

// ─────────────────────────────────────────────────────────────
// CoDriverPage
// ─────────────────────────────────────────────────────────────
export default function CoDriverPage() {
  const [pending, setPending] = useState([]);
  const [myLogs, setMyLogs]   = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchCoDriverData(setPending, setMyLogs, setLoading);
  }, []);

  function load() { fetchCoDriverData(setPending, setMyLogs, setLoading); }

  function handleApprove(primaryId, coId, approve) {
    API.approveCoDriver(primaryId, coId, approve)
      .then(() => load())
      .catch(e => alert(errorMsg(e)));
  }

  return (
    <div className="page">
      {/* Pending approvals panel */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-head">
          <span className="card-head-title">Pending Co-Driver Approvals</span>
          {loading && <span className="spin" />}
        </div>
        <div className="card-body">
          {pending.length === 0
            ? <div className="empty" style={{ padding: 24 }}><p>No pending approvals</p></div>
            : pending.map(sub => (
              <div key={sub.id} className="cd-card">
                <div className="cd-card-head">
                  <div>
                    <div className="cd-name">{sub.driver_name || sub.driver_email}</div>
                    <div className="cd-meta">{fmtDate(sub.day)} · Log #{sub.id}</div>
                  </div>
                  <span className="badge badge-amber">Pending</span>
                </div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text3)" }}>
                  {parseFloat(sub.total_miles_driven||0).toFixed(0)} miles · Driving: {fmtHours(sub.total_hours_driving)}
                </div>
                <div className="cd-actions">
                  <button className="btn btn-success btn-sm"
                    onClick={() => handleApprove(sub.linked_primary_log_id || sub.id, sub.id, true)}>
                    <Icon.Check /> Approve
                  </button>
                  <button className="btn btn-danger btn-sm"
                    onClick={() => handleApprove(sub.linked_primary_log_id || sub.id, sub.id, false)}>
                    <Icon.X /> Reject
                  </button>
                </div>
              </div>
            ))}
        </div>
      </div>

      {/* Submit as co-driver */}
      <div className="card">
        <div className="card-head"><span className="card-head-title">Submit as Co-Driver</span></div>
        <div className="card-body">
          <p style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text3)", marginBottom: 16 }}>
            Select one of your logs from this week and enter the main driver's log ID to request linkage.
          </p>
          <CoDriverSubmitForm myLogs={myLogs} onSubmitted={load} />
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// CoDriverSubmitForm
// ─────────────────────────────────────────────────────────────
function CoDriverSubmitForm({ myLogs, onSubmitted }) {
  const [selectedLog, setSelectedLog] = useState("");
  const [primaryId, setPrimaryId]     = useState("");
  const [loading, setLoading]         = useState(false);
  const [msg, setMsg]                 = useState(null);

  async function submit() {
    if (!selectedLog || !primaryId) return;
    setLoading(true); setMsg(null);
    try {
      await API.submitCoDriver(parseInt(selectedLog), parseInt(primaryId));
      setMsg({ type: "success", text: "Submitted for approval." });
      setSelectedLog(""); setPrimaryId("");
      onSubmitted();
    } catch (e) { setMsg({ type: "err", text: errorMsg(e) }); }
    finally { setLoading(false); }
  }

  return (
    <div>
      {msg && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Your Log</label>
          <select className="form-input form-select" value={selectedLog} onChange={e => setSelectedLog(e.target.value)}>
            <option value="">Select log…</option>
            {myLogs.map(l => (
              <option key={l.id} value={l.id}>{fmtDate(l.day)} — {l.from_location || "Log #"+l.id}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Main Driver's Log ID</label>
          <input className="form-input" placeholder="e.g. 42"
            value={primaryId} onChange={e => setPrimaryId(e.target.value)} />
        </div>
      </div>
      <button className="btn btn-primary" onClick={submit}
        disabled={loading || !selectedLog || !primaryId}>
        {loading ? <span className="spin" /> : "Submit for Approval"}
      </button>
    </div>
  );
}