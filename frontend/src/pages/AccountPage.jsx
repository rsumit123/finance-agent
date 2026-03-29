import { useState, useEffect } from "react";
import { LogOut, Shield, EyeOff, X, Plus } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { getExcludedBanks, setExcludedBanks, getExpenses } from "../api/client";

export default function AccountPage() {
  const { user, logout } = useAuth();
  const [excluded, setExcluded] = useState([]);
  const [allBanks, setAllBanks] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // Load excluded banks and detect available banks from expenses
    getExcludedBanks().then((d) => setExcluded(d.banks || [])).catch(() => {});

    // Get all unique banks from expenses
    const now = new Date();
    const start = new Date(now.getFullYear() - 1, now.getMonth(), 1);
    getExpenses({
      start_date: start.toISOString().split("T")[0],
      end_date: now.toISOString().split("T")[0],
      limit: 5000,
    }).then((data) => {
      const banks = new Set();
      for (const e of data.expenses || []) {
        const bank = extractBank(e.source);
        if (bank) banks.add(bank);
      }
      setAllBanks([...banks].sort());
    }).catch(() => {});
  }, []);

  const toggleBank = async (bank) => {
    setSaving(true);
    const next = excluded.includes(bank)
      ? excluded.filter((b) => b !== bank)
      : [...excluded, bank];
    try {
      await setExcludedBanks(next);
      setExcluded(next);
    } catch {}
    setSaving(false);
  };

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

      {/* Excluded banks */}
      {allBanks.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h2 style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <EyeOff size={18} /> Hidden Banks
          </h2>
          <p style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 14 }}>
            Transactions from hidden banks won't appear in expenses, dashboard, or net worth calculations.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {allBanks.map((bank) => {
              const isExcluded = excluded.includes(bank);
              return (
                <button
                  key={bank}
                  onClick={() => toggleBank(bank)}
                  disabled={saving}
                  style={{
                    padding: "8px 14px",
                    fontSize: 13,
                    fontWeight: 600,
                    borderRadius: 8,
                    border: isExcluded ? "1px solid var(--red)" : "1px solid var(--border)",
                    background: isExcluded ? "var(--red-bg)" : "var(--bg-input)",
                    color: isExcluded ? "var(--red)" : "var(--text)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    opacity: saving ? 0.6 : 1,
                    textTransform: "capitalize",
                  }}
                >
                  {isExcluded ? <X size={14} /> : null}
                  {bank}
                  {isExcluded ? " (hidden)" : ""}
                </button>
              );
            })}
          </div>
          {excluded.length > 0 && (
            <p style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 10 }}>
              Tap a hidden bank to show it again.
            </p>
          )}
        </div>
      )}

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

function extractBank(source) {
  if (!source) return null;
  const s = source.toLowerCase();
  const banks = ["hdfc", "axis", "scapia", "icici", "sbi", "kotak", "karnataka", "canara", "bob", "pnb", "idfc", "yes_bank", "indusind"];
  for (const b of banks) {
    if (s.includes(b)) return b;
  }
  return null;
}
