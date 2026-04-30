import { useState, useEffect } from "react";
import * as API from "../../api/client.js";
import { fmtDate, fmtHours, errorMsg } from "../../hooks/utils.js";
import { Icon } from "../../components/Icons.jsx";
import { DriverLogPicker } from "../logs/LogsPage.jsx";

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
            Select your log, search for the main driver, then pick the shared day from their logs.
          </p>
          <CoDriverSubmitForm myLogs={myLogs} onSubmitted={load} />
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// CoDriverSubmitForm
// Uses the shared DriverLogPicker — no duplicated search logic.
// ─────────────────────────────────────────────────────────────
function CoDriverSubmitForm({ myLogs, onSubmitted }) {
  const [myLogId, setMyLogId]           = useState("");
  const [primaryLogId, setPrimaryLogId] = useState("");
  const [submitting, setSubmitting]     = useState(false);
  const [msg, setMsg]                   = useState(null);

  const myLog = myLogs.find(l => String(l.id) === String(myLogId));

  async function submit() {
    if (!myLogId || !primaryLogId) return;
    setSubmitting(true); setMsg(null);
    try {
      await API.submitCoDriver(parseInt(myLogId), parseInt(primaryLogId));
      setMsg({ type: "success", text: "Submitted for approval. The main driver will be notified." });
      setMyLogId(""); setPrimaryLogId("");
      onSubmitted();
    } catch (e) { setMsg({ type: "err", text: errorMsg(e) }); }
    finally { setSubmitting(false); }
  }

  return (
    <div>
      {msg && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}

      {/* Step 1 — pick your log */}
      <div className="form-group">
        <label className="form-label">Step 1 — Your Log</label>
        <select className="form-input form-select" value={myLogId}
          onChange={e => { setMyLogId(e.target.value); setPrimaryLogId(""); }}>
          <option value="">Select your log for the shared day…</option>
          {myLogs.map(l => (
            <option key={l.id} value={l.id}>
              {fmtDate(l.day)} — {l.from_location || "Log #" + l.id}
            </option>
          ))}
        </select>
      </div>

      {/* Steps 2 + 3 — shared DriverLogPicker */}
      <div className="form-group">
        <label className="form-label">Step 2 — Find Main Driver & Their Log</label>
        <DriverLogPicker
          forDay={myLog?.day || null}
          onPick={setPrimaryLogId}
        />
      </div>

      <button className="btn btn-primary" onClick={submit}
        disabled={submitting || !myLogId || !primaryLogId}>
        {submitting ? <span className="spin" /> : "Submit for Approval"}
      </button>
    </div>
  );
}