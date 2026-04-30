import { useState } from "react";
import * as API from "../../api/client.js";
import { saveTokens } from "../../api/client.js";
import { errorMsg } from "../../hooks/utils.js";

export default function AuthPage({ onAuth }) {
  const [mode, setMode]       = useState("login"); // "login" | "signup"
  const [form, setForm]       = useState({});
  const [err, setErr]         = useState("");
  const [loading, setLoading] = useState(false);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      if (mode === "login") {
        const res = await API.login({ email: form.email, password: form.password });
        saveTokens(res.access, res.refresh);
        onAuth();
      } else {
        await API.signup({
          email:               form.email,
          username:            form.username,
          password:            form.password,
          confirm_password:    form.confirm_password,
          first_name:          form.first_name,
          last_name:           form.last_name,
          designation_number:  form.designation_number || "",
          is_driver:           form.is_driver === "true",
          is_manager:          form.is_manager === "true",
          signup_code:         form.signup_code,
        });
        setMode("login");
        setErr("");
        setForm({});
        alert("Account created! Please log in.");
      }
    } catch (e) { setErr(errorMsg(e)); }
    finally     { setLoading(false); }
  }

  return (
    <div className="auth-shell">
      <div className="auth-bg" />
      <div className="auth-grid" />
      <div className="auth-card">
        <div className="auth-logo">🚚 Anozie's TruckLog</div>
        <div className="auth-tagline">Electronic Driver Log System</div>
        <div className="auth-title">{mode === "login" ? "Sign In" : "Create Account"}</div>

        {err && <div className="auth-err">{err}</div>}

        <form onSubmit={submit}>
          {mode === "signup" && (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">First Name</label>
                  <input className="form-input" required value={form.first_name||""} onChange={e=>set("first_name",e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Last Name</label>
                  <input className="form-input" required value={form.last_name||""} onChange={e=>set("last_name",e.target.value)} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Username</label>
                <input className="form-input" required value={form.username||""} onChange={e=>set("username",e.target.value)} />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Role</label>
                  <select className="form-input form-select" value={form.is_driver||""} onChange={e=>set("is_driver",e.target.value)}>
                    <option value="">Select…</option>
                    <option value="true">Driver</option>
                    <option value="false">Manager</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Designation #</label>
                  <input className="form-input" value={form.designation_number||""} onChange={e=>set("designation_number",e.target.value)} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Signup Code</label>
                <input className="form-input" required placeholder="Required"
                  value={form.signup_code||""} onChange={e=>set("signup_code",e.target.value)} />
              </div>
            </>
          )}

          <div className="form-group">
            <label className="form-label">Email</label>
            <input className="form-input" type="email" required value={form.email||""} onChange={e=>set("email",e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Password</label>
            <input className="form-input" type="password" required value={form.password||""} onChange={e=>set("password",e.target.value)} />
          </div>
          {mode === "signup" && (
            <div className="form-group">
              <label className="form-label">Confirm Password</label>
              <input className="form-input" type="password" required value={form.confirm_password||""} onChange={e=>set("confirm_password",e.target.value)} />
            </div>
          )}

          <button className="btn btn-primary" type="submit"
            style={{ width: "100%", marginTop: 4, justifyContent: "center" }}
            disabled={loading}>
            {loading ? <span className="spin" /> : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <div className="auth-switch">
          {mode === "login"
            ? <>No account? <span onClick={() => { setMode("signup"); setErr(""); }}>Register</span></>
            : <>Have an account? <span onClick={() => { setMode("login"); setErr(""); }}>Sign in</span></>}
        </div>
      </div>
    </div>
  );
}