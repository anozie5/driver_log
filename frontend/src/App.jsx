import { useState, useEffect, useCallback } from "react";
import "./styles/global.css";

import { getToken, clearTokens, getProfile, getPendingCoDrivers } from "./api/client.js";

import { Icon }        from "./components/Icons.jsx";
import AuthPage        from "./pages/auth/AuthPage.jsx";
import LogsPage        from "./pages/logs/LogsPage.jsx";
import CoDriverPage    from "./pages/codriver/CoDriverPage.jsx";
import TripPage        from "./pages/trips/TripPage.jsx";
import ManagerPage     from "./pages/manager/ManagerPage.jsx";
import ProfilePage     from "./pages/profile/ProfilePage.jsx";

// ─── Module-level fetch helper ────────────────────────────────
// Accepts all state setters as arguments so it lives outside the
// component and has no closure over component state — zero
// exhaustive-deps warnings, no stale references.
function fetchUserData(setUser, setPendingCount, setAuthed) {
  getProfile()
    .then(u => {
      setUser(u);
      if (u.is_driver) {
        getPendingCoDrivers()
          .then(p => setPendingCount(p?.length || 0))
          .catch(() => setPendingCount(0));
      }
    })
    .catch(() => {
      clearTokens();
      setAuthed(false);
    });
}

// ─────────────────────────────────────────────────────────────
// App
// ─────────────────────────────────────────────────────────────
export default function App() {
  const [authed, setAuthed]             = useState(!!getToken());
  const [user, setUser]                 = useState(null);
  const [page, setPage]                 = useState("logs");
  const [pendingCount, setPendingCount] = useState(0);

  // Stable reference — setters never change identity between renders,
  // so this useCallback dep array is truly stable and the linter is happy.
  const loadUser = useCallback(() => {
    fetchUserData(setUser, setPendingCount, setAuthed);
  }, []);  // setUser / setPendingCount / setAuthed are stable React setter refs

  useEffect(() => {
    if (authed) loadUser();
  }, [authed, loadUser]);

  function logout() { clearTokens(); setAuthed(false); setUser(null); }

  // ── Auth gate ──────────────────────────────────────────────
  if (!authed) return <AuthPage onAuth={() => setAuthed(true)} />;

  if (!user) return (
    <div className="auth-shell"><span className="spin" /></div>
  );

  const isManager = user.is_manager || user.is_staff;
  const isDriver  = user.is_driver;

  // ── Build navigation items based on role ───────────────────
  const navItems = [
    ...(isDriver ? [
      { id: "logs",     icon: <Icon.Logs />,   label: "My Logs" },
      { id: "codriver", icon: <Icon.Driver />, label: `Co-Driver${pendingCount > 0 ? ` (${pendingCount})` : ""}` },
      { id: "trips",    icon: <Icon.Truck />,  label: "Trip Planner" },
    ] : []),
    ...(isManager ? [
      { id: "manager",  icon: <Icon.Dash />,   label: "Driver Overview" },
    ] : []),
    { id: "profile",  icon: <Icon.Profile />, label: "Profile" },
  ];

  const pageTitle = {
    logs:     "Daily Logs",
    codriver: "Co-Driver",
    trips:    "Trip Planner",
    manager:  "Driver Overview",
    profile:  "Profile",
  };

  return (
    <div className="shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sb-logo">
          <div className="sb-logo-mark">🚚 Anozie's TruckLog</div>
          <div className="sb-logo-sub">ELD System</div>
        </div>
        <nav className="sb-nav">
          <div className="sb-section">Navigation</div>
          {navItems.map(item => (
            <div key={item.id}
              className={`sb-item${page === item.id ? " active" : ""}`}
              onClick={() => setPage(item.id)}>
              {item.icon}
              {item.label}
            </div>
          ))}
        </nav>
        <div className="sb-user">
          <div className="sb-user-name">{user.first_name || user.username}</div>
          <div className="sb-user-role">
            {isManager ? "Manager" : "Driver"} · {user.designation_number || user.email?.split("@")[0]}
          </div>
          <button className="sb-logout" onClick={logout}>Sign Out</button>
        </div>
      </aside>

      {/* Main content */}
      <main className="main">
        <div className="topbar">
          <div>
            <div className="topbar-title">{pageTitle[page]}</div>
            <div className="topbar-sub">
              {new Date().toLocaleDateString("en-US", {
                weekday: "long", month: "long", day: "numeric", year: "numeric",
              })}
            </div>
          </div>
        </div>

        {page === "logs"     && <LogsPage     user={user} />}
        {page === "codriver" && <CoDriverPage />}
        {page === "trips"    && <TripPage />}
        {page === "manager"  && <ManagerPage />}
        {page === "profile"  && <ProfilePage user={user} onUpdated={loadUser} />}
      </main>
    </div>
  );
}