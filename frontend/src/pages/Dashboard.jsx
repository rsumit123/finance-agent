import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { getExpenseSummary, getBudgetStatus, getSubscriptions, getNetworth } from "../api/client";

const COLORS = [
  "#6366f1", "#22c55e", "#eab308", "#ef4444", "#f97316",
  "#06b6d4", "#ec4899", "#8b5cf6", "#14b8a6", "#f43f5e",
];

function formatINR(n) {
  if (n == null) return "₹0";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function getMonthRange(year, month) {
  const start = `${year}-${String(month).padStart(2, "0")}-01`;
  const lastDay = new Date(year, month, 0).getDate();
  const end = `${year}-${String(month).padStart(2, "0")}-${lastDay}`;
  return { start, end };
}

function getWeekRange(offset = 0) {
  const now = new Date();
  const start = new Date(now);
  start.setDate(now.getDate() - now.getDay() + 1 + offset * 7); // Monday
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return {
    start: start.toISOString().split("T")[0],
    end: end.toISOString().split("T")[0],
  };
}

function formatMonthLabel(year, month) {
  return new Date(year, month - 1).toLocaleString("en-IN", { month: "long", year: "numeric" });
}

function formatWeekLabel(startStr) {
  const s = new Date(startStr);
  const e = new Date(s);
  e.setDate(s.getDate() + 6);
  return `${s.getDate()} ${s.toLocaleString("en-IN", { month: "short" })} — ${e.getDate()} ${e.toLocaleString("en-IN", { month: "short", year: "numeric" })}`;
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [budget, setBudget] = useState(null);
  const [subscriptions, setSubscriptions] = useState([]);
  const [networth, setNetworth] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // Period state
  const [mode, setMode] = useState("month"); // "week" or "month"
  const now = new Date();
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [weekOffset, setWeekOffset] = useState(0);

  const dateRange = mode === "month"
    ? getMonthRange(selectedYear, selectedMonth)
    : getWeekRange(weekOffset);

  const periodLabel = mode === "month"
    ? formatMonthLabel(selectedYear, selectedMonth)
    : formatWeekLabel(dateRange.start);

  const isCurrentPeriod = mode === "month"
    ? (selectedYear === now.getFullYear() && selectedMonth === now.getMonth() + 1)
    : weekOffset === 0;

  useEffect(() => {
    setLoading(true);
    const params = { start_date: dateRange.start, end_date: dateRange.end };
    Promise.all([
      getExpenseSummary(params).then(setSummary).catch(() => {}),
      getBudgetStatus().then(setBudget).catch(() => {}),
      getSubscriptions().then(setSubscriptions).catch(() => {}),
      getNetworth(params).then(setNetworth).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [selectedYear, selectedMonth, weekOffset, mode]);

  const goBack = () => {
    if (mode === "month") {
      if (selectedMonth === 1) { setSelectedMonth(12); setSelectedYear(selectedYear - 1); }
      else setSelectedMonth(selectedMonth - 1);
    } else {
      setWeekOffset(weekOffset - 1);
    }
  };

  const goForward = () => {
    if (isCurrentPeriod) return;
    if (mode === "month") {
      if (selectedMonth === 12) { setSelectedMonth(1); setSelectedYear(selectedYear + 1); }
      else setSelectedMonth(selectedMonth + 1);
    } else {
      setWeekOffset(weekOffset + 1);
    }
  };

  const goToNow = () => {
    setSelectedYear(now.getFullYear());
    setSelectedMonth(now.getMonth() + 1);
    setWeekOffset(0);
  };

  const drillDown = (category) => {
    navigate("/expenses", {
      state: {
        category,
        mode,
        year: selectedYear,
        month: selectedMonth,
        weekOffset,
      },
    });
  };

  const categoryData = summary
    ? Object.entries(summary.by_category).map(([name, value]) => ({ name, value })).filter(d => d.value > 0)
    : [];

  const paymentData = summary
    ? Object.entries(summary.by_payment_method).map(([name, value]) => ({ name: name.replace(/_/g, " "), value })).filter(d => d.value > 0)
    : [];

  if (loading) {
    return (
      <div>
        <div className="page-header"><h1>Dashboard</h1></div>
        <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>Loading...</div>
      </div>
    );
  }

  return (
    <div>
      {/* Header with period controls */}
      <div className="page-header" style={{ marginBottom: 16 }}>
        <h1>Dashboard</h1>
      </div>

      {/* Period picker */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "var(--bg-card)", border: "1px solid var(--border)",
        borderRadius: 10, padding: "8px 12px", marginBottom: 20, flexWrap: "wrap", gap: 8,
      }}>
        <div style={{ display: "flex", gap: 4 }}>
          <button
            className={mode === "week" ? "" : "secondary"}
            onClick={() => setMode("week")}
            style={{ padding: "6px 12px", fontSize: 12, minHeight: 32 }}
          >
            Weekly
          </button>
          <button
            className={mode === "month" ? "" : "secondary"}
            onClick={() => setMode("month")}
            style={{ padding: "6px 12px", fontSize: 12, minHeight: 32 }}
          >
            Monthly
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button className="secondary" onClick={goBack} style={{ padding: "4px 8px", minHeight: 32 }}>
            <ChevronLeft size={16} />
          </button>
          <span style={{ fontSize: 14, fontWeight: 600, minWidth: 140, textAlign: "center" }}>
            {periodLabel}
          </span>
          <button className="secondary" onClick={goForward} disabled={isCurrentPeriod} style={{ padding: "4px 8px", minHeight: 32 }}>
            <ChevronRight size={16} />
          </button>
        </div>

        {!isCurrentPeriod && (
          <button className="secondary" onClick={goToNow} style={{ padding: "4px 10px", fontSize: 11, minHeight: 32 }}>
            Today
          </button>
        )}
      </div>

      {/* Net Worth / Financial Summary */}
      {networth && (networth.total_spent > 0 || networth.total_income > 0 || networth.total_cc_debt > 0) && (
        <div className="card" style={{ marginBottom: 20, padding: "16px 20px" }}>
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Net Cash Flow
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, color: networth.net_cashflow >= 0 ? "var(--green)" : "var(--red)" }}>
                {networth.net_cashflow >= 0 ? "+" : ""}{formatINR(networth.net_cashflow)}
              </div>
            </div>
            {networth.total_income > 0 && (
              <div>
                <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Income</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: "var(--green)" }}>+{formatINR(networth.total_income)}</div>
              </div>
            )}
            <div>
              <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Spent</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{formatINR(networth.total_spent)}</div>
            </div>
            {networth.total_transfers > 0 && (
              <div>
                <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Transfers</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text-dim)" }}>{formatINR(networth.total_transfers)}</div>
              </div>
            )}
            {networth.total_cc_debt > 0 && (
              <div>
                <div style={{ fontSize: 11, color: "var(--text-dim)" }}>CC Outstanding (All Time)</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: "var(--red)" }}>{formatINR(networth.total_cc_debt)}</div>
              </div>
            )}
          </div>
          {Object.keys(networth.cc_outstanding || {}).length > 0 && (
            <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
              {Object.entries(networth.cc_outstanding).map(([bank, info]) => (
                <span key={bank} style={{
                  fontSize: 11, padding: "3px 10px", borderRadius: 6,
                  background: info.outstanding > 0 ? "var(--red-bg)" : "var(--green-bg)",
                  color: info.outstanding > 0 ? "var(--red)" : "var(--green)",
                }}>
                  {bank}: {info.outstanding > 0 ? formatINR(info.outstanding) + " due" : "Paid up"}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

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
                color: budget.weekly_percent > 100 ? "var(--red)" : budget.weekly_percent > 75 ? "var(--yellow)" : "var(--green)"
              }}>
                {formatINR(budget.weekly_remaining)}
              </div>
              <div className="sub">{budget.weekly_percent.toFixed(0)}% used of {formatINR(budget.weekly_limit)}</div>
              <div className="progress-bar">
                <div className="progress-fill" style={{
                  width: `${Math.min(budget.weekly_percent, 100)}%`,
                  background: budget.weekly_percent > 100 ? "var(--red)" : budget.weekly_percent > 75 ? "var(--yellow)" : "var(--green)",
                }} />
              </div>
            </div>
            <div className="stat-card">
              <div className="label">Monthly Budget</div>
              <div className="value" style={{
                color: budget.monthly_percent > 100 ? "var(--red)" : budget.monthly_percent > 75 ? "var(--yellow)" : "var(--green)"
              }}>
                {formatINR(budget.monthly_remaining)}
              </div>
              <div className="sub">{budget.monthly_percent.toFixed(0)}% used of {formatINR(budget.monthly_limit)}</div>
              <div className="progress-bar">
                <div className="progress-fill" style={{
                  width: `${Math.min(budget.monthly_percent, 100)}%`,
                  background: budget.monthly_percent > 100 ? "var(--red)" : budget.monthly_percent > 75 ? "var(--yellow)" : "var(--green)",
                }} />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Category Breakdown — horizontal bars instead of pie chart */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2>Spending by Category</h2>
        {categoryData.length > 0 ? (
          <div>
            {categoryData
              .sort((a, b) => b.value - a.value)
              .map((item, i) => {
                const maxVal = categoryData[0]?.value || 1;
                const pct = ((item.value / (summary?.expense || 1)) * 100).toFixed(0);
                return (
                  <div
                    key={item.name}
                    onClick={() => drillDown(item.name)}
                    style={{ marginBottom: 10, cursor: "pointer", padding: "6px 8px", borderRadius: 8, transition: "background 0.15s" }}
                    onMouseEnter={(e) => e.currentTarget.style.background = "var(--bg-input)"}
                    onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, textTransform: "capitalize", display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ width: 8, height: 8, borderRadius: "50%", background: COLORS[i % COLORS.length], flexShrink: 0 }} />
                        {item.name}
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                        {formatINR(item.value)}
                        <span style={{ fontSize: 11, color: "var(--text-dim)", fontWeight: 400 }}>{pct}%</span>
                        <ChevronRight size={14} style={{ color: "var(--text-dim)" }} />
                      </span>
                    </div>
                    <div style={{ height: 6, background: "var(--bg-input)", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{
                        height: "100%", borderRadius: 3,
                        width: `${(item.value / maxVal) * 100}%`,
                        background: COLORS[i % COLORS.length],
                        transition: "width 0.3s",
                      }} />
                    </div>
                  </div>
                );
              })}
          </div>
        ) : (
          <p style={{ color: "var(--text-dim)" }}>No expenses for this period</p>
        )}
      </div>

      {/* Payment Method — compact pills instead of bar chart */}
      {paymentData.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h2>By Payment Method</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {paymentData
              .sort((a, b) => b.value - a.value)
              .map((item, i) => (
                <div key={item.name} style={{
                  flex: "1 1 auto", minWidth: 100,
                  background: "var(--bg-input)", borderRadius: 10, padding: "12px 14px",
                  textAlign: "center",
                }}>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{formatINR(item.value)}</div>
                  <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2, textTransform: "capitalize" }}>{item.name}</div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Recurring Payments */}
      {subscriptions.length > 0 && (
        <div className="card" style={{ marginTop: 24 }}>
          <h2>Recurring Payments</h2>
          <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 16 }}>
            Auto-detected — {formatINR(subscriptions.reduce((sum, s) => sum + s.amount, 0))}/month estimated
          </p>
          <table className="responsive-table">
            <thead><tr><th>Service</th><th>Amount</th><th>Last Charged</th><th>Occurrences</th><th>Total Spent</th></tr></thead>
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
