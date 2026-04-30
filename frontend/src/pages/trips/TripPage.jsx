import { useState, useEffect } from "react";
import * as API from "../../api/client.js";
import { fmtDate, fmtTime, fmtHours, errorMsg } from "../../hooks/utils.js";
import { Icon } from "../../components/Icons.jsx";
import Modal from "../../components/Modal.jsx";
import ActivityGrid from "../../components/ActivityGrid.jsx";

const STOP_COLORS = {
  start:         "var(--success)",
  pickup:        "var(--amber)",
  dropoff:       "var(--danger)",
  fuel:          "var(--info)",
  rest_break:    "var(--text2)",
  sleeper_break: "var(--sleeping)",
};

// ─── Module-level fetch helpers ───────────────────────────────
function fetchTrips(setTrips, setLoading) {
  setLoading(true);
  API.getTrips()
    .then(setTrips)
    .catch(() => {})
    .finally(() => setLoading(false));
}

function fetchTrip(id, setSelected) {
  API.getTrip(id).then(setSelected).catch(() => {});
}

// ─────────────────────────────────────────────────────────────
// TripPage — list + detail view
// ─────────────────────────────────────────────────────────────
export default function TripPage() {
  const [trips, setTrips]       = useState([]);
  const [loading, setLoading]   = useState(false);
  const [selected, setSelected] = useState(null);
  const [showPlan, setShowPlan] = useState(false);

  useEffect(() => {
    fetchTrips(setTrips, setLoading);
  }, []);

  function load()        { fetchTrips(setTrips, setLoading); }
  function openTrip(id)  { fetchTrip(id, setSelected); }

  if (selected) {
    return (
      <TripDetail
        trip={selected}
        onBack={() => setSelected(null)}
        onDelete={async () => { await API.deleteTrip(selected.id); setSelected(null); load(); }}
      />
    );
  }

  return (
    <div className="page">
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 20 }}>
        <button className="btn btn-primary" onClick={() => setShowPlan(true)}>
          <Icon.Plus /> Plan Trip
        </button>
      </div>

      <div className="card">
        <div className="card-head">
          <span className="card-head-title">Trip History</span>
          {loading && <span className="spin" />}
        </div>
        <div className="table-wrap">
          {trips.length === 0 && !loading
            ? <div className="empty"><div className="empty-icon">🚛</div><p>No trips planned yet</p></div>
            : (
              <table>
                <thead>
                  <tr>
                    <th>#</th><th>Route</th><th>Departure</th>
                    <th>Distance</th><th>Drive Time</th><th>Status</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {trips.map(t => (
                    <tr key={t.id}>
                      <td className="mono">{t.id}</td>
                      <td style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {t.current_location} → {t.dropoff_location}
                      </td>
                      <td className="mono">{fmtDate(t.departure_time)}</td>
                      <td className="mono">{t.total_distance_miles ? parseFloat(t.total_distance_miles).toFixed(0)+" mi" : "—"}</td>
                      <td className="mono">{t.total_driving_hours ? fmtHours(t.total_driving_hours) : "—"}</td>
                      <td>
                        <span className={`badge ${t.status==="computed"?"badge-green":t.status==="failed"?"badge-red":"badge-amber"}`}>
                          {t.status}
                        </span>
                      </td>
                      <td>
                        <button className="btn btn-ghost btn-sm" onClick={() => openTrip(t.id)}>View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </div>
      </div>

      {showPlan && (
        <PlanTripModal
          onClose={() => setShowPlan(false)}
          onPlanned={trip => { setShowPlan(false); load(); setSelected(trip); }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// TripDetail — full trip view with stops timeline + ELD logs
// ─────────────────────────────────────────────────────────────
function TripDetail({ trip, onBack, onDelete }) {
  return (
    <div className="page">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <button className="btn btn-ghost btn-sm" onClick={onBack}>← Back</button>
        <span style={{ fontSize: 16, fontWeight: 700 }}>Trip #{trip.id}</span>
        <span className={`badge ${trip.status==="computed"?"badge-green":trip.status==="failed"?"badge-red":"badge-amber"}`}>
          {trip.status}
        </span>
        <button className="btn btn-danger btn-sm" style={{ marginLeft: "auto" }} onClick={onDelete}>
          Delete Trip
        </button>
      </div>

      {/* Summary stats */}
      <div className="stat-row" style={{ marginBottom: 20 }}>
        {[
          ["Distance",  `${parseFloat(trip.total_distance_miles||0).toFixed(0)} mi`],
          ["Drive Time", fmtHours(trip.total_driving_hours)],
          ["Stops",      trip.stops?.length || 0],
          ["ELD Days",   trip.day_logs?.length || 0],
        ].map(([l,v]) => (
          <div key={l} className="stat-card">
            <div className="stat-label">{l}</div>
            <div className="stat-value" style={{ fontSize: 20 }}>{v}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* Route info */}
        <div className="card">
          <div className="card-head"><span className="card-head-title">Route Info</span></div>
          <div className="card-body">
            {[
              ["From",      trip.current_location],
              ["Pickup",    trip.pickup_location],
              ["Dropoff",   trip.dropoff_location],
              ["Departure", `${fmtDate(trip.departure_time)} ${fmtTime(trip.departure_time)}`],
              ["Cycle Used",`${trip.current_cycle_used} hrs`],
            ].map(([k,v]) => (
              <div key={k} style={{ marginBottom: 12 }}>
                <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text3)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 2 }}>{k}</div>
                <div style={{ fontSize: 13, color: "var(--text)" }}>{v}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Stops timeline */}
        <div className="card">
          <div className="card-head"><span className="card-head-title">Stops ({trip.stops?.length || 0})</span></div>
          <div className="card-body" style={{ maxHeight: 380, overflowY: "auto" }}>
            <div className="timeline">
              {(trip.stops || []).map((stop, i) => (
                <div key={stop.id} className="tl-item">
                  <div className="tl-spine">
                    <div className="tl-dot" style={{ background: STOP_COLORS[stop.stop_type] || "var(--text3)" }} />
                    {i < trip.stops.length - 1 && <div className="tl-line" />}
                  </div>
                  <div className="tl-content">
                    <div className="tl-stop-type">{stop.stop_type_display || stop.stop_type}</div>
                    <div className="tl-location">{stop.location}</div>
                    <div className="tl-meta">
                      {stop.arrival_time && fmtTime(stop.arrival_time)}
                      {stop.duration_hours > 0 && ` · ${fmtHours(stop.duration_hours)}`}
                      {stop.cumulative_miles > 0 && ` · ${parseFloat(stop.cumulative_miles).toFixed(0)} mi`}
                    </div>
                    {stop.notes && (
                      <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text3)", marginTop: 2 }}>
                        {stop.notes}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ELD day logs */}
      {trip.day_logs?.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-head"><span className="card-head-title">Generated ELD Logs</span></div>
          <div className="card-body">
            {trip.day_logs.map(({ day_number, day_log }) => (
              <div key={day_number} style={{ marginBottom: 28 }}>
                <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--amber)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 10 }}>
                  Day {day_number} — {fmtDate(day_log?.day)}
                </div>
                {day_log && (
                  <>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: 12 }}>
                      {[
                        ["Driving",  fmtHours(day_log.total_hours_driving)],
                        ["On Duty",  fmtHours(day_log.total_hours_on_duty)],
                        ["Off Duty", fmtHours(day_log.total_hours_off_duty)],
                        ["Sleeper",  fmtHours(day_log.total_hours_sleeping)],
                      ].map(([l,v]) => (
                        <div key={l} style={{ background: "var(--bg3)", padding: "10px 12px", borderRadius: "var(--radius)" }}>
                          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text3)", marginBottom: 4 }}>{l}</div>
                          <div style={{ fontFamily: "var(--mono)", fontSize: 14, fontWeight: 700, color: "var(--text)" }}>{v}</div>
                        </div>
                      ))}
                    </div>
                    <ActivityGrid actLogs={day_log.act_logs} day={day_log.day} />
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// PlanTripModal — 4-input form that triggers the full pipeline
// ─────────────────────────────────────────────────────────────
function PlanTripModal({ onClose, onPlanned }) {
  const [form, setForm] = useState({
    departure_time: new Date().toISOString().slice(0, 16),
    current_cycle_used: 0,
  });
  const [err, setErr]   = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function submit() {
    setErr(""); setLoading(true);
    try {
      const res = await API.planTrip({
        ...form,
        departure_time: form.departure_time + ":00Z",
        current_cycle_used: parseFloat(form.current_cycle_used),
      });
      onPlanned(res);
    } catch (e) { setErr(errorMsg(e)); }
    finally { setLoading(false); }
  }

  return (
    <Modal title="Plan New Trip" onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={submit} disabled={loading}>
          {loading ? <><span className="spin" />&nbsp;Planning…</> : <><Icon.Truck /> Plan Trip</>}
        </button>
      </>}>
      {err && <div className="alert alert-err">{err}</div>}
      {loading && (
        <div className="alert" style={{ background: "rgba(245,166,35,.08)", border: "1px solid rgba(245,166,35,.2)", color: "var(--amber)", marginBottom: 16 }}>
          ⏳ Geocoding locations and computing HOS schedule… this may take a few seconds.
        </div>
      )}
      <div className="form-group">
        <label className="form-label">Current Location</label>
        <input className="form-input" placeholder="e.g. Chicago, IL"
          value={form.current_location||""} onChange={e=>set("current_location",e.target.value)} />
      </div>
      <div className="form-group">
        <label className="form-label">Pickup Location</label>
        <input className="form-input" placeholder="e.g. St. Louis, MO"
          value={form.pickup_location||""} onChange={e=>set("pickup_location",e.target.value)} />
      </div>
      <div className="form-group">
        <label className="form-label">Dropoff Location</label>
        <input className="form-input" placeholder="e.g. Dallas, TX"
          value={form.dropoff_location||""} onChange={e=>set("dropoff_location",e.target.value)} />
      </div>
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Departure Time</label>
          <input type="datetime-local" className="form-input"
            value={form.departure_time||""} onChange={e=>set("departure_time",e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Cycle Hours Used (0–70)</label>
          <input type="number" min="0" max="70" step="0.5" className="form-input"
            value={form.current_cycle_used} onChange={e=>set("current_cycle_used",e.target.value)} />
        </div>
      </div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text3)", background: "var(--bg3)", padding: "10px 12px", borderRadius: "var(--radius)" }}>
        HOS rules: 70hr/8-day cycle · 11hr driving · 14hr window · 30-min break after 8hrs · Fuel ≤1,000 mi · 1hr pickup + 1hr dropoff
      </div>
    </Modal>
  );
}