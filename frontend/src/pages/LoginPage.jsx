import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Wallet, Loader, Smartphone, Mail, FileText, Brain, TrendingUp, Shield, ChevronDown } from "lucide-react";
import { Capacitor } from "@capacitor/core";
import { useAuth } from "../auth/AuthContext";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
const isNative = Capacitor.isNativePlatform();

const FEATURES = [
  {
    icon: Smartphone,
    title: "SMS Auto-Import",
    desc: "Reads bank SMS alerts instantly. Every spend, every credit, captured automatically.",
    color: "#22c55e",
  },
  {
    icon: Mail,
    title: "Gmail Sync",
    desc: "Pulls transaction emails and statement PDFs from your inbox. One tap, fully synced.",
    color: "#3b82f6",
  },
  {
    icon: Brain,
    title: "Smart Categories",
    desc: "18 categories with learning. It gets smarter the more you use it.",
    color: "#a855f7",
  },
  {
    icon: TrendingUp,
    title: "Net Worth Tracking",
    desc: "Bank balances, CC debt, salary, and spending — all in one clear view.",
    color: "#f59e0b",
  },
  {
    icon: FileText,
    title: "Statement Parser",
    desc: "Upload HDFC, Axis, ICICI, Kotak, Scapia PDFs. Password-protected? No problem.",
    color: "#ec4899",
  },
  {
    icon: Shield,
    title: "Private by Design",
    desc: "Your data stays yours. No ads, no selling data. Open source backend.",
    color: "#6366f1",
  },
];

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 48 48">
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

  // Initialize native Google Auth
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
          if (data.token) {
            login(data.token);
          } else {
            setError(data.detail || "Login failed");
          }
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

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0f1117",
      overflowX: "hidden",
    }}>
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-8px); }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse-glow {
          0%, 100% { opacity: 0.6; }
          50% { opacity: 1; }
        }
        .login-feature-card:hover {
          border-color: rgba(99, 102, 241, 0.3) !important;
          transform: translateY(-2px);
        }
        .login-cta-btn:hover {
          transform: scale(1.02);
          box-shadow: 0 8px 32px rgba(99, 102, 241, 0.3) !important;
        }
      `}</style>

      {/* Hero Section */}
      <div style={{
        position: "relative",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "60px 20px 40px",
      }}>
        {/* Background glow orb */}
        <div style={{
          position: "absolute",
          top: "15%",
          left: "50%",
          transform: "translateX(-50%)",
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(99,102,241,0.15) 0%, rgba(99,102,241,0.05) 40%, transparent 70%)",
          pointerEvents: "none",
          animation: "pulse-glow 4s ease-in-out infinite",
        }} />

        {/* Logo */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 24,
          animation: "fadeUp 0.6s ease-out both",
        }}>
          <div style={{
            width: 48,
            height: 48,
            borderRadius: 14,
            background: "linear-gradient(135deg, #6366f1, #818cf8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 4px 20px rgba(99,102,241,0.3)",
          }}>
            <Wallet size={26} color="white" />
          </div>
          <span style={{
            fontSize: 32,
            fontWeight: 800,
            letterSpacing: "-0.02em",
            background: "linear-gradient(135deg, #e4e6f0, #8b8fa3)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>
            MoneyFlow
          </span>
        </div>

        {/* Tagline */}
        <h1 style={{
          fontSize: "clamp(22px, 5vw, 36px)",
          fontWeight: 700,
          textAlign: "center",
          lineHeight: 1.3,
          maxWidth: 480,
          marginBottom: 12,
          color: "#e4e6f0",
          animation: "fadeUp 0.6s ease-out 0.1s both",
        }}>
          Your money, tracked{" "}
          <span style={{ color: "#6366f1" }}>automatically</span>
        </h1>

        <p style={{
          fontSize: "clamp(14px, 3vw, 16px)",
          color: "#8b8fa3",
          textAlign: "center",
          maxWidth: 400,
          lineHeight: 1.6,
          marginBottom: 36,
          animation: "fadeUp 0.6s ease-out 0.2s both",
        }}>
          Auto-imports from SMS, Gmail, and bank statements.
          Smart categorization. Real-time net worth.
        </p>

        {/* Sign in button */}
        <div style={{ animation: "fadeUp 0.6s ease-out 0.3s both", width: "100%", maxWidth: 360 }}>
          <button
            className="login-cta-btn"
            onClick={handleGoogleLogin}
            disabled={signingIn}
            style={{
              width: "100%",
              padding: "16px 24px",
              fontSize: 16,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              background: "white",
              color: "#1a1a1a",
              border: "none",
              borderRadius: 12,
              cursor: "pointer",
              opacity: signingIn ? 0.7 : 1,
              transition: "all 0.2s ease",
              boxShadow: "0 4px 16px rgba(0,0,0,0.2)",
            }}
          >
            <GoogleIcon />
            {signingIn ? "Signing in..." : "Continue with Google"}
          </button>

          {error && (
            <p style={{ color: "#ef4444", fontSize: 13, marginTop: 12, textAlign: "center" }}>{error}</p>
          )}
        </div>

        {/* Scroll hint */}
        <div style={{
          marginTop: "auto",
          paddingTop: 40,
          animation: "fadeUp 0.6s ease-out 0.5s both",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 4,
        }}>
          <span style={{ fontSize: 11, color: "#8b8fa3", letterSpacing: "0.1em", textTransform: "uppercase" }}>
            How it works
          </span>
          <ChevronDown size={16} style={{ color: "#8b8fa3", animation: "float 2s ease-in-out infinite" }} />
        </div>
      </div>

      {/* Features Section */}
      <div style={{
        padding: "40px 20px 60px",
        maxWidth: 720,
        margin: "0 auto",
      }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 12,
        }}>
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className="login-feature-card"
              style={{
                background: "#1a1d27",
                border: "1px solid #2d3040",
                borderRadius: 14,
                padding: "22px 20px",
                transition: "all 0.2s ease",
                animation: `fadeUp 0.5s ease-out ${0.1 * i}s both`,
              }}
            >
              <div style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 14,
              }}>
                <div style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: `${f.color}15`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <f.icon size={20} style={{ color: f.color }} />
                </div>
                <div>
                  <div style={{
                    fontSize: 15,
                    fontWeight: 650,
                    color: "#e4e6f0",
                    marginBottom: 4,
                  }}>
                    {f.title}
                  </div>
                  <div style={{
                    fontSize: 13,
                    lineHeight: 1.5,
                    color: "#8b8fa3",
                  }}>
                    {f.desc}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom CTA */}
        <div style={{
          textAlign: "center",
          marginTop: 48,
          animation: "fadeUp 0.5s ease-out 0.6s both",
        }}>
          <p style={{ fontSize: 13, color: "#8b8fa3", marginBottom: 20 }}>
            Works with HDFC, Axis, ICICI, SBI, Kotak, Scapia, and more
          </p>
          <button
            className="login-cta-btn"
            onClick={handleGoogleLogin}
            disabled={signingIn}
            style={{
              padding: "14px 32px",
              fontSize: 15,
              fontWeight: 600,
              background: "linear-gradient(135deg, #6366f1, #818cf8)",
              color: "white",
              border: "none",
              borderRadius: 12,
              cursor: "pointer",
              opacity: signingIn ? 0.7 : 1,
              transition: "all 0.2s ease",
              boxShadow: "0 4px 20px rgba(99,102,241,0.25)",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            Get Started Free
          </button>
          <p style={{ fontSize: 11, color: "#666", marginTop: 16 }}>
            {isNative ? "SMS + Gmail access requested only when you choose to sync." : "Gmail access requested only when you choose to sync."}
          </p>
        </div>
      </div>
    </div>
  );
}

export function LoginCallback() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState("Connecting to server...");

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      setStatus("Signing you in...");
      login(token);
      setTimeout(() => navigate("/", { replace: true }), 500);
    } else {
      setStatus("No token received. Redirecting...");
      setTimeout(() => navigate("/login", { replace: true }), 1000);
    }
  }, [searchParams, login, navigate]);

  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 16,
      background: "#0f1117", padding: 20,
    }}>
      <div style={{
        background: "#1a1d27", border: "1px solid #2d3040",
        borderRadius: 16, padding: "48px 40px", textAlign: "center",
        maxWidth: 360, width: "100%",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 20 }}>
          <Wallet size={28} style={{ color: "#6366f1" }} />
          <span style={{ fontSize: 22, fontWeight: 700, color: "#6366f1" }}>MoneyFlow</span>
        </div>
        <Loader size={28} style={{ color: "#6366f1", animation: "spin 1s linear infinite", marginBottom: 16 }} />
        <p style={{ color: "#8b8fa3", fontSize: 14 }}>{status}</p>
      </div>
    </div>
  );
}
