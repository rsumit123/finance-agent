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
  Legend,
  ResponsiveContainer,
} from "recharts";
import { getExpenseSummary, getBudgetStatus, getSubscriptions } from "../api/client";

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
  const [subscriptions, setSubscriptions] = useState([]);
  const [period, setPeriod] = useState("month");

  useEffect(() => {
    getExpenseSummary(period).then(setSummary).catch(() => {});
    getBudgetStatus().then(setBudget).catch(() => {});
    getSubscriptions().then(setSubscriptions).catch(() => {});
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
          <div className="label">Spent</div>
          <div className="value">{formatINR(summary?.expense)}</div>
          <div className="sub">{summary?.count || 0} transactions</div>
        </div>
        {summary?.income > 0 && (
          <div className="stat-card">
            <div className="label">Received</div>
            <div className="value" style={{ color: "var(--green)" }}>+{formatINR(summary?.income)}</div>
            <div className="sub">Net: {formatINR(summary?.total)}</div>
          </div>
        )}
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
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="45%"
                  outerRadius={80}
                  dataKey="value"
                  label={false}
                >
                  {categoryData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => formatINR(v)} />
                <Legend
                  verticalAlign="bottom"
                  iconType="circle"
                  iconSize={8}
                  formatter={(value, entry) => {
                    const item = categoryData.find(d => d.name === value);
                    return `${value} (${formatINR(item?.value)})`;
                  }}
                  wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                />
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
              <BarChart data={paymentData} margin={{ left: -20, right: 8 }}>
                <XAxis dataKey="name" stroke="var(--text-dim)" fontSize={11} tick={{ fill: "var(--text-dim)" }} />
                <YAxis stroke="var(--text-dim)" fontSize={11} tick={{ fill: "var(--text-dim)" }} width={50} />
                <Tooltip formatter={(v) => formatINR(v)} />
                <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: "var(--text-dim)" }}>No expenses yet</p>
          )}
        </div>
      </div>

      {/* Recurring Payments */}
      {subscriptions.length > 0 && (
        <div className="card" style={{ marginTop: 24 }}>
          <h2>Recurring Payments</h2>
          <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 16 }}>
            Auto-detected from your transaction history — {formatINR(subscriptions.reduce((sum, s) => sum + s.amount, 0))}/month estimated
          </p>
          <table className="responsive-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Amount</th>
                <th>Last Charged</th>
                <th>Occurrences</th>
                <th>Total Spent</th>
              </tr>
            </thead>
            <tbody>
              {subscriptions.map((s, i) => (
                <tr key={i}>
                  <td data-label="Service" style={{ fontWeight: 600 }}>{s.name}</td>
                  <td data-label="Amount">{formatINR(s.amount)}</td>
                  <td data-label="Last Charged">{s.last_charged}</td>
                  <td data-label="Occurrences">{s.occurrence_count}x</td>
                  <td data-label="Total Spent">{formatINR(s.total_spent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
