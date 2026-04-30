import { useState } from "react";
import * as API from "../../api/client.js";
import { errorMsg } from "../../hooks/utils.js";

export default function ProfilePage({ user, onUpdated }) {
  const [tab, setTab]           = useState("profile");
  const [form, setForm]         = useState({ ...user });
  const [pwForm, setPwForm]     = useState({});
  const [emailForm, setEmailForm] = useState({});
  const [msg, setMsg]           = useState(null);
  const [loading, setLoading]   = useState(false);

  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }));

  function switchTab(t) { setTab(t); setMsg(null); }

  async function saveProfile() {
    setLoading(true); setMsg(null);
    try {
      await API.updateProfile({
        username:           form.username,
        first_name:         form.first_name,
        last_name:          form.last_name,
        designation_number: form.designation_number,
      });
      setMsg({ type: "success", text: "Profile updated." });
      onUpdated();
    } catch (e) { setMsg({ type: "err", text: errorMsg(e) }); }
    finally { setLoading(false); }
  }

  async function savePw() {
    setLoading(true); setMsg(null);
    try {
      await API.resetPassword(pwForm);
      setMsg({ type: "success", text: "Password updated." });
      setPwForm({});
    } catch (e) { setMsg({ type: "err", text: errorMsg(e) }); }
    finally { setLoading(false); }
  }

  async function saveEmail() {
    setLoading(true); setMsg(null);
    try {
      await API.changeEmail(emailForm);
      setMsg({ type: "success", text: "Email updated. Please log in again." });
    } catch (e) { setMsg({ type: "err", text: errorMsg(e) }); }
    finally { setLoading(false); }
  }

  return (
    <div className="page" style={{ maxWidth: 560 }}>
      <div className="tabs">
        {[["profile","Profile"],["password","Password"],["email","Email"]].map(([v,l]) => (
          <div key={v} className={`tab${tab===v?" active":""}`} onClick={() => switchTab(v)}>{l}</div>
        ))}
      </div>

      {msg && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}

      {tab === "profile" && (
        <div className="card">
          <div className="card-body">
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">First Name</label>
                <input className="form-input" value={form.first_name||""} onChange={e=>setF("first_name",e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Last Name</label>
                <input className="form-input" value={form.last_name||""} onChange={e=>setF("last_name",e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Username</label>
              <input className="form-input" value={form.username||""} onChange={e=>setF("username",e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Designation Number</label>
              <input className="form-input" value={form.designation_number||""} onChange={e=>setF("designation_number",e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Email (read-only)</label>
              <input className="form-input" value={form.email||""} readOnly style={{ opacity: .5 }} />
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              {form.is_driver  && <span className="badge badge-amber">Driver</span>}
              {form.is_manager && <span className="badge badge-blue">Manager</span>}
            </div>
            <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={saveProfile} disabled={loading}>
              {loading ? <span className="spin" /> : "Save Changes"}
            </button>
          </div>
        </div>
      )}

      {tab === "password" && (
        <div className="card">
          <div className="card-body">
            <div className="form-group">
              <label className="form-label">New Password</label>
              <input type="password" className="form-input"
                value={pwForm.new_password||""} onChange={e=>setPwForm(f=>({...f,new_password:e.target.value}))} />
            </div>
            <div className="form-group">
              <label className="form-label">Confirm Password</label>
              <input type="password" className="form-input"
                value={pwForm.confirm_password||""} onChange={e=>setPwForm(f=>({...f,confirm_password:e.target.value}))} />
            </div>
            <button className="btn btn-primary" onClick={savePw} disabled={loading}>
              {loading ? <span className="spin" /> : "Update Password"}
            </button>
          </div>
        </div>
      )}

      {tab === "email" && (
        <div className="card">
          <div className="card-body">
            <div className="form-group">
              <label className="form-label">Current Password</label>
              <input type="password" className="form-input"
                value={emailForm.current_password||""} onChange={e=>setEmailForm(f=>({...f,current_password:e.target.value}))} />
            </div>
            <div className="form-group">
              <label className="form-label">New Email</label>
              <input type="email" className="form-input"
                value={emailForm.new_email||""} onChange={e=>setEmailForm(f=>({...f,new_email:e.target.value}))} />
            </div>
            <button className="btn btn-primary" onClick={saveEmail} disabled={loading}>
              {loading ? <span className="spin" /> : "Update Email"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}