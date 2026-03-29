import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Wallet, Loader, Smartphone, Mail, PieChart, Shield, ArrowRight } from "lucide-react";
import { Capacitor } from "@capacitor/core";
import { useAuth } from "../auth/AuthContext";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
const isNative = Capacitor.isNativePlatform();

const GoogleIcon = () => (
  <svg width="20" height="20" viewBox="0 0 48 48">
    <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z" />
    <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z" />
    <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z" />
    <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z" />
  </svg>
);

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [signingIn, setSigningIn] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [user, navigate]);

  useEffect(() => {
    if (!isNative) return;
    try {
      import("@codetrix-studio/capacitor-google-auth").then(({ GoogleAuth }) => {
        GoogleAuth.initialize({
          clientId: GOOGLE_CLIENT_ID,
          scopes: ["profile", "email"],
          grantOfflineAccess: false,
        });
      }).catch((err) => console.error("GoogleAuth init error:", err));
    } catch (err) {
      console.error("GoogleAuth import error:", err);
    }
  }, []);

  const handleGoogleLogin = async () => {
    setSigningIn(true);
    setError("");
    if (isNative) {
      try {
        const { GoogleAuth } = await import("@codetrix-studio/capacitor-google-auth");
        const googleUser = await GoogleAuth.signIn();
        if (googleUser?.authentication?.idToken) {
          const res = await fetch(`${API_URL}/api/auth/google/token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: googleUser.authentication.idToken }),
          });
          const data = await res.json();
          if (data.token) login(data.token);
          else setError(data.detail || "Login failed");
        }
      } catch (err) {
        console.error("Native sign-in error:", err);
        setError("Google Sign-In failed. Try again.");
      }
    } else {
      try {
        const res = await fetch(`${API_URL}/api/auth/google`);
        const { auth_url } = await res.json();
        window.location.href = auth_url;
      } catch {
        setError("Failed to connect to server");
      }
    }
    setSigningIn(false);
  };

  const features = [
    { icon: Smartphone, text: "Auto-import from SMS", color: "#22c55e" },
    { icon: Mail, text: "Sync Gmail & statements", color: "#3b82f6" },
    { icon: PieChart, text: "Smart categorization", color: "#a855f7" },
    { icon: Shield, text: "Private & secure", color: "#6366f1" },
  ];

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0c13",
      display: "flex",
      flexDirection: "column",
      position: "relative",
      overflow: "hidden",
    }}>
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes shimmer {
          0% { background-position: -200% center; }
          100% { background-position: 200% center; }
        }
        @keyframes glow-rotate {
          0% { transform: translate(-50%, -50%) rotate(0deg); }
          100% { transform: translate(-50%, -50%) rotate(360deg); }
        }
        .mf-google-btn {
          transition: all 0.2s ease;
        }
        .mf-google-btn:active {
          transform: scale(0.98);
        }
      `}</style>

      {/* Ambient background */}
      <div style={{
        position: "absolute", top: "-20%", left: "50%",
        width: "140vw", height: "140vw", maxWidth: 600, maxHeight: 600,
        transform: "translate(-50%, 0)",
        borderRadius: "50%",
        background: "radial-gradient(ellipse, rgba(99,102,241,0.08) 0%, rgba(99,102,241,0.03) 35%, transparent 65%)",
        pointerEvents: "none",
      }} />
      <div style={{
        position: "absolute", bottom: "10%", right: "-10%",
        width: 300, height: 300,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(34,197,94,0.04) 0%, transparent 60%)",
        pointerEvents: "none",
      }} />

      {/* Content */}
      <div style={{
        flex: 1, display: "flex", flexDirection: "column",
        justifyContent: "center", alignItems: "center",
        padding: "60px 24px 32px",
        position: "relative", zIndex: 1,
      }}>

        {/* Logo mark */}
        <div style={{
          width: 56, height: 56, borderRadius: 16,
          background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
          display: "flex", alignItems: "center", justifyContent: "center",
          marginBottom: 20,
          boxShadow: "0 8px 32px rgba(99,102,241,0.25), 0 0 0 1px rgba(99,102,241,0.1)",
          animation: "fadeIn 0.5s ease-out both",
        }}>
          <Wallet size={28} color="white" strokeWidth={2.2} />
        </div>

        {/* Title */}
        <h1 style={{
          fontSize: 28, fontWeight: 800, color: "#f0f0f5",
          textAlign: "center", lineHeight: 1.2, marginBottom: 8,
          letterSpacing: "-0.03em",
          animation: "fadeIn 0.5s ease-out 0.08s both",
        }}>
          MoneyFlow
        </h1>

        {/* Subtitle */}
        <p style={{
          fontSize: 15, color: "#7a7f96", textAlign: "center",
          lineHeight: 1.5, maxWidth: 300, marginBottom: 40,
          animation: "fadeIn 0.5s ease-out 0.15s both",
        }}>
          Know exactly where your money goes.
          <br />Auto-tracked from your bank messages.
        </p>

        {/* Feature pills — compact horizontal layout */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr",
          gap: 10, width: "100%", maxWidth: 340,
          marginBottom: 40,
          animation: "fadeIn 0.5s ease-out 0.22s both",
        }}>
          {features.map((f) => (
            <div key={f.text} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "12px 14px",
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: 12,
            }}>
              <f.icon size={16} style={{ color: f.color, flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: "#b0b4c8", fontWeight: 500, lineHeight: 1.3 }}>
                {f.text}
              </span>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div style={{
          width: "100%", maxWidth: 340,
          animation: "fadeIn 0.5s ease-out 0.3s both",
        }}>
          <button
            className="mf-google-btn"
            onClick={handleGoogleLogin}
            disabled={signingIn}
            style={{
              width: "100%",
              padding: "15px 20px",
              fontSize: 15,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 10,
              background: "#fff",
              color: "#1a1a1a",
              border: "none",
              borderRadius: 14,
              cursor: "pointer",
              opacity: signingIn ? 0.7 : 1,
              boxShadow: "0 2px 12px rgba(0,0,0,0.15), 0 0 0 1px rgba(255,255,255,0.08)",
              minHeight: 52,
              letterSpacing: "-0.01em",
            }}
          >
            <GoogleIcon />
            {signingIn ? "Signing in..." : "Continue with Google"}
            {!signingIn && <ArrowRight size={16} style={{ marginLeft: 2, opacity: 0.5 }} />}
          </button>

          {error && (
            <p style={{ color: "#ef4444", fontSize: 13, marginTop: 10, textAlign: "center" }}>{error}</p>
          )}
        </div>
      </div>

      {/* Bottom section */}
      <div style={{
        padding: "0 24px 40px",
        textAlign: "center",
        animation: "fadeIn 0.5s ease-out 0.4s both",
      }}>
        {/* Bank support */}
        <div style={{
          display: "flex", flexWrap: "wrap", justifyContent: "center",
          gap: "6px 10px", marginBottom: 16,
        }}>
          {["HDFC", "Axis", "ICICI", "SBI", "Kotak", "Scapia"].map((bank) => (
            <span key={bank} style={{
              fontSize: 11, fontWeight: 600, color: "#4a4e64",
              padding: "4px 8px", borderRadius: 6,
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.04)",
              letterSpacing: "0.02em",
            }}>
              {bank}
            </span>
          ))}
        </div>

        <p style={{
          fontSize: 11, color: "#3d4055", lineHeight: 1.5,
          maxWidth: 280, margin: "0 auto",
        }}>
          Your data stays on our servers. We never sell or share it.
          {isNative && " SMS and Gmail access is requested only when you choose."}
        </p>
      </div>
    </div>
  );
}

export function LoginCallback() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState("Connecting...");

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      setStatus("Signing you in...");
      login(token);
      setTimeout(() => navigate("/", { replace: true }), 500);
    } else {
      setStatus("Redirecting...");
      setTimeout(() => navigate("/login", { replace: true }), 1000);
    }
  }, [searchParams, login, navigate]);

  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      background: "#0a0c13", padding: 20,
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 14,
        background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
        display: "flex", alignItems: "center", justifyContent: "center",
        marginBottom: 20,
        boxShadow: "0 8px 32px rgba(99,102,241,0.25)",
      }}>
        <Wallet size={24} color="white" />
      </div>
      <Loader size={24} style={{ color: "#6366f1", animation: "spin 1s linear infinite", marginBottom: 14 }} />
      <p style={{ color: "#7a7f96", fontSize: 14 }}>{status}</p>
    </div>
  );
}
