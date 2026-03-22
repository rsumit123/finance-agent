import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Receipt,
  Upload,
  ShoppingCart,
  Wallet,
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import Expenses from "./pages/Expenses";
import UploadPage from "./pages/UploadPage";
import Advisor from "./pages/Advisor";
import BudgetPage from "./pages/BudgetPage";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <div className="logo">
            <Wallet size={28} />
            <span>Finance Agent</span>
          </div>
          <div className="nav-links">
            <NavLink to="/" end>
              <LayoutDashboard size={20} />
              Dashboard
            </NavLink>
            <NavLink to="/expenses">
              <Receipt size={20} />
              Expenses
            </NavLink>
            <NavLink to="/upload">
              <Upload size={20} />
              Upload Statement
            </NavLink>
            <NavLink to="/advisor">
              <ShoppingCart size={20} />
              Can I Buy?
            </NavLink>
            <NavLink to="/budget">
              <Wallet size={20} />
              Budget
            </NavLink>
          </div>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/expenses" element={<Expenses />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/advisor" element={<Advisor />} />
            <Route path="/budget" element={<BudgetPage />} />
          </Routes>
        </main>
        <nav className="bottom-bar">
          <NavLink to="/" end>
            <LayoutDashboard size={20} />
            Dashboard
          </NavLink>
          <NavLink to="/expenses">
            <Receipt size={20} />
            Expenses
          </NavLink>
          <NavLink to="/upload">
            <Upload size={20} />
            Upload
          </NavLink>
          <NavLink to="/advisor">
            <ShoppingCart size={20} />
            Buy?
          </NavLink>
          <NavLink to="/budget">
            <Wallet size={20} />
            Budget
          </NavLink>
        </nav>
      </div>
    </BrowserRouter>
  );
}

export default App;
