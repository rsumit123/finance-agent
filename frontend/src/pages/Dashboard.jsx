import { useState, useEffect } from "react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { getExpenseSummary, getBudgetStatus } from "../api/client";

const COLORS = [
  "#6366f1", "#22c55e", "#eab308", "#ef4444", "#f97316",
  "#06b6d4", "#ec4899", "#8b5cf6", "#14b8a6", "#f43f5e",
];

function formatINR(n) {
  if (n == null) return "₹0";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [budget, setBudget] = useState(null);
  const [period, setPeriod] = useState("month");

  useEffect(() => {
    getExpenseSummary(period).then(setSummary).catch(() => {});
    getBudgetStatus().then(setBudget).catch(() => {});
  }, [period]);

  const categoryData = summary
    ? Object.entries(summary.by_category).map(([name, value]) => ({
        name,
        value,
      }))
    : [];

  const paymentData = summary
    ? Object.entries(summary.by_payment_method).map(([name, value]) => ({
        name: name.replace("_", " "),
        value,
      }))
    : [];

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Your financial overview at a glance</p>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <button
          className={period === "week" ? "" : "secondary"}
          onClick={() => setPeriod("week")}
        >
          This Week
        </button>
        <button
          className={period === "month" ? "" : "secondary"}
          onClick={() => setPeriod("month")}
        >
          This Month
        </button>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="label">Total Spent</div>
          <div className="value">{formatINR(summary?.total)}</div>
          <div className="sub">{summary?.count || 0} transactions</div>
        </div>
        {budget && (
          <>
            <div className="stat-card">
              <div className="label">Weekly Budget</div>
              <div className="value" style={{
                color: budget.weekly_percent > 100 ? "var(--red)"
                     : budget.weekly_percent > 75 ? "var(--yellow)"
                     : "var(--green)"
              }}>
                {formatINR(budget.weekly_remaining)}
              </div>
              <div className="sub">
                {budget.weekly_percent.toFixed(0)}% used of {formatINR(budget.weekly_limit)}
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${Math.min(budget.weekly_percent, 100)}%`,
                    background: budget.weekly_percent > 100 ? "var(--red)"
                      : budget.weekly_percent > 75 ? "var(--yellow)"
                      : "var(--green)",
                  }}
                />
              </div>
            </div>
            <div className="stat-card">
              <div className="label">Monthly Budget</div>
              <div className="value" style={{
                color: budget.monthly_percent > 100 ? "var(--red)"
                     : budget.monthly_percent > 75 ? "var(--yellow)"
                     : "var(--green)"
              }}>
                {formatINR(budget.monthly_remaining)}
              </div>
              <div className="sub">
                {budget.monthly_percent.toFixed(0)}% used of {formatINR(budget.monthly_limit)}
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${Math.min(budget.monthly_percent, 100)}%`,
                    background: budget.monthly_percent > 100 ? "var(--red)"
                      : budget.monthly_percent > 75 ? "var(--yellow)"
                      : "var(--green)",
                  }}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Charts */}
      <div className="grid-2">
        <div className="card">
          <h2>Spending by Category</h2>
          {categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  dataKey="value"
                  label={({ name, percent }) =>
                    `${name} (${(percent * 100).toFixed(0)}%)`
                  }
                >
                  {categoryData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => formatINR(v)} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: "var(--text-dim)" }}>No expenses yet</p>
          )}
        </div>

        <div className="card">
          <h2>By Payment Method</h2>
          {paymentData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={paymentData}>
                <XAxis dataKey="name" stroke="var(--text-dim)" fontSize={12} />
                <YAxis stroke="var(--text-dim)" fontSize={12} />
                <Tooltip formatter={(v) => formatINR(v)} />
                <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: "var(--text-dim)" }}>No expenses yet</p>
          )}
        </div>
      </div>
    </div>
  );
}
