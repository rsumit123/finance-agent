import { LogOut, Mail, Shield } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

export default function AccountPage() {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <div>
      <div className="page-header">
        <h1>Account</h1>
      </div>

      {/* Profile card */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {user.picture && (
            <img
              src={user.picture}
              alt=""
              style={{ width: 56, height: 56, borderRadius: "50%" }}
              referrerPolicy="no-referrer"
            />
          )}
          <div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{user.name}</div>
            <div style={{ fontSize: 14, color: "var(--text-dim)", marginTop: 2 }}>{user.email}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 6 }}>
              <Shield size={12} style={{ color: "var(--green)" }} />
              <span style={{ fontSize: 11, color: "var(--green)" }}>Signed in with Google</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sign out */}
      <div className="card" style={{ borderColor: "var(--red)" }}>
        <button
          className="danger"
          onClick={logout}
          style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "14px 20px", fontSize: 15 }}
        >
          <LogOut size={18} /> Sign Out
        </button>
        <p style={{ fontSize: 12, color: "var(--text-dim)", textAlign: "center", marginTop: 12 }}>
          Your data is stored securely and will be here when you sign back in.
        </p>
      </div>
    </div>
  );
}
