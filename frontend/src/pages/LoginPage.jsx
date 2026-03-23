import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Wallet } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // If already logged in, redirect to dashboard
  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [user, navigate]);

  const handleGoogleLogin = async () => {
    try {
      const res = await fetch(`${API_URL}/api/auth/google`);
      const { auth_url } = await res.json();
      window.location.href = auth_url;
    } catch {
      alert("Failed to connect to server");
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "var(--bg)", padding: 20,
    }}>
      <div style={{
        background: "var(--bg-card)", border: "1px solid var(--border)",
        borderRadius: 16, padding: "48px 40px", textAlign: "center",
        maxWidth: 400, width: "100%",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 8 }}>
          <Wallet size={32} style={{ color: "var(--accent)" }} />
          <span style={{ fontSize: 24, fontWeight: 700, color: "var(--accent)" }}>MoneyFlow</span>
        </div>
        <p style={{ color: "var(--text-dim)", marginBottom: 32, fontSize: 14 }}>
          Track expenses, import bank statements, manage budgets
        </p>

        <button
          onClick={handleGoogleLogin}
          style={{
            width: "100%", padding: "14px 20px", fontSize: 15, fontWeight: 600,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
            background: "white", color: "#333", border: "1px solid #ddd",
            borderRadius: 10, cursor: "pointer",
          }}
        >
          <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"/><path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"/><path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"/><path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"/></svg>
          Sign in with Google
        </button>

        <p style={{ color: "var(--text-dim)", fontSize: 11, marginTop: 24 }}>
          Your data is private. We only read bank alert emails when you explicitly connect Gmail.
        </p>
      </div>
    </div>
  );
}

export function LoginCallback() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      login(token);
      navigate("/", { replace: true });
    } else {
      navigate("/login", { replace: true });
    }
  }, [searchParams, login, navigate]);

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-dim)" }}>
      Signing you in...
    </div>
  );
}
