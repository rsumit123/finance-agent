import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import {
  LayoutDashboard, Receipt, Upload, ShoppingCart, Wallet, CreditCard, LogOut,
} from "lucide-react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import Dashboard from "./pages/Dashboard";
import Expenses from "./pages/Expenses";
import UploadPage from "./pages/UploadPage";
import Advisor from "./pages/Advisor";
import BudgetPage from "./pages/BudgetPage";
import StatementsPage from "./pages/StatementsPage";
import LoginPage, { LoginCallback } from "./pages/LoginPage";
import AccountPage from "./pages/AccountPage";
import "./App.css";

function ProtectedApp() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-dim)" }}>
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app">
      <nav className="sidebar">
        <div className="logo">
          <Wallet size={28} />
          <span>MoneyFlow</span>
        </div>
        <div className="nav-links">
          <NavLink to="/" end><LayoutDashboard size={20} /> Dashboard</NavLink>
          <NavLink to="/expenses"><Receipt size={20} /> Expenses</NavLink>
          <NavLink to="/upload"><Upload size={20} /> Import</NavLink>
          <NavLink to="/statements"><CreditCard size={20} /> Statements</NavLink>
          <NavLink to="/advisor"><ShoppingCart size={20} /> Can I Buy?</NavLink>
          <NavLink to="/budget"><Wallet size={20} /> Budget</NavLink>
        </div>
        <div style={{ marginTop: "auto", padding: "0 8px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            {user.picture && <img src={user.picture} alt="" style={{ width: 28, height: 28, borderRadius: "50%" }} referrerPolicy="no-referrer" />}
            <span style={{ fontSize: 12, color: "var(--text-dim)", overflow: "hidden", textOverflow: "ellipsis" }}>{user.name || user.email}</span>
          </div>
          <button className="secondary" onClick={logout} style={{ width: "100%", fontSize: 12, padding: "6px 10px", display: "flex", alignItems: "center", gap: 6, justifyContent: "center" }}>
            <LogOut size={14} /> Sign Out
          </button>
        </div>
      </nav>
      <main className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/expenses" element={<Expenses />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/statements" element={<StatementsPage />} />
          <Route path="/advisor" element={<Advisor />} />
          <Route path="/budget" element={<BudgetPage />} />
          <Route path="/account" element={<AccountPage />} />
        </Routes>
      </main>
      <nav className="bottom-bar">
        <NavLink to="/" end><LayoutDashboard size={20} /> Home</NavLink>
        <NavLink to="/expenses"><Receipt size={20} /> Expenses</NavLink>
        <NavLink to="/upload"><Upload size={20} /> Import</NavLink>
        <NavLink to="/statements"><CreditCard size={20} /> Cards</NavLink>
        <NavLink to="/account">
          {user.picture
            ? <img src={user.picture} alt="" style={{ width: 20, height: 20, borderRadius: "50%" }} referrerPolicy="no-referrer" />
            : <Wallet size={20} />
          }
          Account
        </NavLink>
      </nav>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/login/callback" element={<LoginCallback />} />
          <Route path="/*" element={<ProtectedApp />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
