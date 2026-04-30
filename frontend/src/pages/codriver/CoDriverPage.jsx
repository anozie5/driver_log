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
// 3-step flow:
//   1. Pick your own log
//   2. Search for the main driver by name / email
//   3. Pick their log for the same day → submit
// ─────────────────────────────────────────────────────────────
function CoDriverSubmitForm({ myLogs, onSubmitted }) {
  const [myLogId, setMyLogId]           = useState("");
  const [search, setSearch]             = useState("");
  const [drivers, setDrivers]           = useState([]);      // search results
  const [searching, setSearching]       = useState(false);
  const [selectedDriver, setSelectedDriver] = useState(null);
  const [driverLogs, setDriverLogs]     = useState([]);      // that driver's logs
  const [loadingLogs, setLoadingLogs]   = useState(false);
  const [primaryLogId, setPrimaryLogId] = useState("");
  const [submitting, setSubmitting]     = useState(false);
  const [msg, setMsg]                   = useState(null);

  // Step 2 — search drivers by typing name or email
  function handleSearch(e) {
    const val = e.target.value;
    setSearch(val);
    setSelectedDriver(null);
    setDriverLogs([]);
    setPrimaryLogId("");

    if (val.trim().length < 2) { setDrivers([]); return; }

    setSearching(true);
    // Use the managers/drivers endpoint — filters server-side by name/email
    // via the query param. Falls back to listing all drivers if no filter param.
    API.searchDrivers(val)
      .then(results => setDrivers(results || []))
      .catch(() => setDrivers([]))
      .finally(() => setSearching(false));
  }

  // Step 3 — once a driver is selected, load their logs
  function selectDriver(driver) {
    setSelectedDriver(driver);
    setSearch(driver.name || driver.email);
    setDrivers([]);
    setPrimaryLogId("");
    setLoadingLogs(true);

    // Fetch the last 30 days of that driver's logs so the co-driver
    // can find the shared day without needing to know the log ID.
    API.getDriverPublicLogs(driver.id, { period: "this_month" })
      .then(logs => setDriverLogs(logs || []))
      .catch(() => setDriverLogs([]))
      .finally(() => setLoadingLogs(false));
  }

  async function submit() {
    if (!myLogId || !primaryLogId) return;
    setSubmitting(true); setMsg(null);
    try {
      await API.submitCoDriver(parseInt(myLogId), parseInt(primaryLogId));
      setMsg({ type: "success", text: "Submitted for approval. The main driver will be notified." });
      setMyLogId(""); setSearch(""); setSelectedDriver(null);
      setDriverLogs([]); setPrimaryLogId("");
      onSubmitted();
    } catch (e) { setMsg({ type: "err", text: errorMsg(e) }); }
    finally { setSubmitting(false); }
  }

  // Find the selected day from my log so we can highlight matching driver logs
  const myLog = myLogs.find(l => String(l.id) === String(myLogId));

  return (
    <div>
      {msg && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}

      {/* Step 1 — your log */}
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

      {/* Step 2 — search for main driver */}
      <div className="form-group" style={{ position: "relative" }}>
        <label className="form-label">Step 2 — Search for Main Driver</label>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input className="form-input" placeholder="Type name, email or designation number…"
            value={search} onChange={handleSearch}
            style={{ flex: 1 }} />
          {searching && <span className="spin" style={{ flexShrink: 0 }} />}
          {selectedDriver && (
            <span className="badge badge-green" style={{ flexShrink: 0 }}>
              {selectedDriver.name || selectedDriver.email}
            </span>
          )}
        </div>

        {/* Dropdown results */}
        {drivers.length > 0 && (
          <div style={{
            position: "absolute", top: "100%", left: 0, right: 0, zIndex: 50,
            background: "var(--bg2)", border: "1px solid var(--border)",
            borderRadius: "var(--radius)", marginTop: 4,
            maxHeight: 200, overflowY: "auto",
          }}>
            {drivers.map(d => (
              <div key={d.id} onClick={() => selectDriver(d)} style={{
                padding: "10px 14px", cursor: "pointer",
                borderBottom: "1px solid var(--border)",
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--bg3)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                    {d.name || d.email}
                  </div>
                  <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text3)" }}>
                    {d.email} · {d.designation_number || "No designation"}
                  </div>
                </div>
                <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text3)" }}>
                  {d.total_logs} logs
                </span>
              </div>
            ))}
          </div>
        )}

        {search.length >= 2 && !searching && drivers.length === 0 && !selectedDriver && (
          <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text3)", marginTop: 6 }}>
            No drivers found matching "{search}"
          </div>
        )}
      </div>

      {/* Step 3 — pick their log for the shared day */}
      {selectedDriver && (
        <div className="form-group">
          <label className="form-label">
            Step 3 — Select {selectedDriver.name || selectedDriver.email}'s Log
            {myLog && <span style={{ color: "var(--amber)", marginLeft: 6 }}>
              (looking for {fmtDate(myLog.day)})
            </span>}
          </label>

          {loadingLogs
            ? <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 0" }}>
                <span className="spin" /><span style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text3)" }}>Loading their logs…</span>
              </div>
            : driverLogs.length === 0
              ? <div style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text3)", padding: "8px 0" }}>
                  No logs found for this driver this month.
                </div>
              : (
                <select className="form-input form-select" value={primaryLogId}
                  onChange={e => setPrimaryLogId(e.target.value)}>
                  <option value="">Select their log…</option>
                  {driverLogs.map(l => {
                    const isMatch = myLog && l.day === myLog.day;
                    return (
                      <option key={l.id} value={l.id}>
                        {isMatch ? "✓ " : ""}{fmtDate(l.day)} — {l.from_location || "Log #" + l.id}
                        {isMatch ? " (same day as yours)" : ""}
                      </option>
                    );
                  })}
                </select>
              )}
        </div>
      )}

      {/* Submit */}
      <button className="btn btn-primary" onClick={submit}
        disabled={submitting || !myLogId || !primaryLogId}>
        {submitting ? <span className="spin" /> : "Submit for Approval"}
      </button>
    </div>
  );
}