import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Info, Mail, Upload, ArrowRight, Wallet, Smartphone } from "lucide-react";
import { Capacitor } from "@capacitor/core";
import { getExpenseSummary, getBudgetStatus, getSubscriptions, getNetworth, getInsights, getExpenses } from "../api/client";

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
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recentTxns, setRecentTxns] = useState([]);
  const [hasAnyData, setHasAnyData] = useState(null); // null = unknown, true/false = checked
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

  // One-time check: does user have any data at all?
  useEffect(() => {
    if (hasAnyData !== null) return;
    getExpenseSummary({ start_date: "2020-01-01", end_date: "2030-12-31" })
      .then((s) => setHasAnyData(s && s.count > 0))
      .catch(() => setHasAnyData(false));
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = { start_date: dateRange.start, end_date: dateRange.end };
    Promise.all([
      getExpenseSummary(params).then(setSummary).catch(() => {}),
      getBudgetStatus().then(setBudget).catch(() => {}),
      getSubscriptions().then(setSubscriptions).catch(() => {}),
      getNetworth(params).then(setNetworth).catch(() => {}),
      getInsights(params).then(setInsights).catch(() => {}),
      getExpenses({ start_date: dateRange.start, end_date: dateRange.end, limit: 5 }).then((data) => {
        setRecentTxns(Array.isArray(data) ? data : (data.expenses || []));
      }).catch(() => {}),
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

  const drillDown = (category, txnType = "") => {
    navigate("/expenses", {
      state: {
        category,
        txnType,
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
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", gap: 12 }}>
            {[1,2,3].map(i => <div key={i} className="loading-skeleton" style={{ flex: 1, height: 80 }} />)}
          </div>
          <div className="loading-skeleton" style={{ height: 200 }} />
          <div className="loading-skeleton" style={{ height: 120 }} />
        </div>
      </div>
    );
  }

  // Onboarding: only show when user has NO data at all (not just empty period)
  const hasPeriodData = summary && summary.count > 0;
  const isNative = Capacitor.isNativePlatform();
  if (hasAnyData === false) {
    return (
      <div>
        <div className="page-header"><h1>Dashboard</h1></div>
        <div className="card" style={{ textAlign: "center", padding: "48px 24px" }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14, margin: "0 auto 16px",
            background: "linear-gradient(135deg, #6366f1, #818cf8)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Wallet size={28} style={{ color: "#fff" }} />
          </div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--text)", marginBottom: 8 }}>Welcome to MoneyFlow</h2>
          <p style={{ color: "var(--text-dim)", marginBottom: 24, maxWidth: 400, margin: "0 auto 24px", lineHeight: 1.6 }}>
            Get started by importing your transactions{isNative ? " via SMS, Gmail, or PDF" : " from Gmail or a PDF statement"} — we'll auto-categorize everything.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 320, margin: "0 auto" }}>
            {isNative && (
              <button
                onClick={() => navigate("/upload")}
                style={{ width: "100%", padding: "14px 20px", fontSize: 15, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
              >
                <Smartphone size={18} /> Sync from SMS <ArrowRight size={16} />
              </button>
            )}
            <button
              onClick={() => navigate("/upload")}
              style={{ width: "100%", padding: "14px 20px", fontSize: 15, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
            >
              <Mail size={18} /> Connect Gmail <ArrowRight size={16} />
            </button>
            <button
              className="secondary"
              onClick={() => navigate("/upload")}
              style={{ width: "100%", padding: "12px 20px", fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
            >
              <Upload size={16} /> Or upload a PDF statement
            </button>
          </div>

          <div style={{ marginTop: 32, maxWidth: 340, margin: "32px auto 0", textAlign: "left" }}>
            {[
              "Import transactions via SMS, Gmail, or PDF",
              "We auto-categorize everything",
              "See your spending dashboard",
            ].map((step, i) => (
              <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 12 }}>
                <span style={{
                  width: 24, height: 24, borderRadius: "50%", flexShrink: 0,
                  background: "rgba(99,102,241,0.15)", color: "var(--accent)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 12, fontWeight: 700,
                }}>{i + 1}</span>
                <span style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.6 }}>{step}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 24, display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
            {["HDFC", "Axis", "ICICI", "Kotak", "Scapia", "SBI"].map((bank) => (
              <span key={bank} style={{ fontSize: 11, padding: "3px 10px", borderRadius: 4, background: "rgba(99,102,241,0.1)", color: "var(--accent)" }}>
                {bank}
              </span>
            ))}
          </div>
          <p style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 8 }}>Supported banks</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header with period controls */}
      <div className="page-header" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <h1>Dashboard</h1>
          <DashboardInfo />
        </div>
      </div>

      {/* Period picker — compact single row */}
      <div style={{
        display: "flex", alignItems: "center", gap: 6,
        background: "var(--bg-card)", border: "1px solid var(--border)",
        borderRadius: 10, padding: "6px 10px", marginBottom: 20,
      }}>
        <button
          className={mode === "week" ? "" : "secondary"}
          onClick={() => setMode("week")}
          style={{ padding: "4px 10px", fontSize: 11, minHeight: 28 }}
        >W</button>
        <button
          className={mode === "month" ? "" : "secondary"}
          onClick={() => setMode("month")}
          style={{ padding: "4px 10px", fontSize: 11, minHeight: 28 }}
        >M</button>
        <div style={{ flex: 1 }} />
        <button className="secondary" onClick={goBack} style={{ padding: "2px 6px", minHeight: 28 }}>
          <ChevronLeft size={14} />
        </button>
        <span style={{ fontSize: 13, fontWeight: 600, minWidth: 120, textAlign: "center" }}>
          {periodLabel}
        </span>
        <button className="secondary" onClick={goForward} disabled={isCurrentPeriod} style={{ padding: "2px 6px", minHeight: 28 }}>
          <ChevronRight size={14} />
        </button>
        {!isCurrentPeriod && (
          <button className="secondary" onClick={goToNow} style={{ padding: "3px 8px", fontSize: 10, minHeight: 28, marginLeft: 2 }}>
            Today
          </button>
        )}
      </div>

      {/* Empty period message */}
      {!hasPeriodData && (
        <div className="card" style={{ textAlign: "center", padding: "32px 20px", marginBottom: 20 }}>
          <div style={{ fontSize: 14, color: "var(--text-dim)", marginBottom: 8 }}>No transactions in this period</div>
          <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Try switching to Monthly or navigate to a different {mode === "week" ? "week" : "month"}.</div>
        </div>
      )}

      {/* Period stats */}
      {hasPeriodData && <div className="stats-scroll">
        <div className="stat-card">
          <div className="label">Spent (excl. transfers)</div>
          <div className="value">{formatINR(summary?.expense)}</div>
          <div className="sub">{summary?.count || 0} transactions{summary?.transfers > 0 ? ` · ${formatINR(summary.transfers)} in transfers` : ""}</div>
        </div>
        {summary?.income > 0 && (
          <div className="stat-card" onClick={() => drillDown("salary")} style={{ cursor: "pointer" }}>
            <div className="label">Salary</div>
            <div className="value" style={{ color: "var(--green)" }}>+{formatINR(summary?.income)}</div>
            <div className="sub" style={{ display: "flex", alignItems: "center", gap: 4 }}>
              Tap to view <ChevronRight size={12} />
            </div>
          </div>
        )}
        {networth && networth.net_cashflow !== 0 && (
          <div className="stat-card">
            <div className="label">Net ({summary?.income > 0 ? "salary - spent" : "this period"})</div>
            <div className="value" style={{ color: networth.net_cashflow >= 0 ? "var(--green)" : "var(--red)" }}>
              {networth.net_cashflow >= 0 ? "+" : ""}{formatINR(networth.net_cashflow)}
            </div>
          </div>
        )}
        {budget && budget.monthly_limit > 0 && (
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
      </div>}

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
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4, opacity: item.name === "transfer" ? 0.5 : 1 }}>
                      <span style={{ fontSize: 13, textTransform: "capitalize", display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ width: 8, height: 8, borderRadius: "50%", background: COLORS[i % COLORS.length], flexShrink: 0 }} />
                        {item.name === "transfer" ? "Self-transfers (excluded)" : item.name === "personal care" ? "Personal Care" : item.name.charAt(0).toUpperCase() + item.name.slice(1)}
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

      {/* Spending pace + Period comparison */}
      {hasPeriodData && mode === "month" && (() => {
        const daysPassed = Math.max(1, Math.min(new Date().getDate(), new Date(selectedYear, selectedMonth, 0).getDate()));
        const totalDays = new Date(selectedYear, selectedMonth, 0).getDate();
        const dailyAvg = (summary?.expense || 0) / daysPassed;
        const projected = dailyAvg * totalDays;
        const daysLeft = isCurrentPeriod ? totalDays - daysPassed : 0;
        return (
          <div className="grid-2" style={{ marginBottom: 20 }}>
            <div className="card">
              <h2>Spending Pace</h2>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{formatINR(dailyAvg)}<span style={{ fontSize: 13, fontWeight: 400, color: "var(--text-dim)" }}>/day</span></div>
              {isCurrentPeriod && daysLeft > 0 && (
                <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 6 }}>
                  Projected: {formatINR(projected)} by month end ({daysLeft} days left)
                </div>
              )}
            </div>
            {insights?.vs_previous?.change_pct != null && (
              <div className="card" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: insights.vs_previous.change_pct <= 0 ? "var(--green)" : "var(--red)" }}>
                  {insights.vs_previous.change_pct <= 0 ? "↓" : "↑"} {Math.abs(insights.vs_previous.change_pct)}%
                </div>
                <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>
                  vs last {mode === "week" ? "week" : "month"} ({formatINR(insights.vs_previous.previous)})
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* Day of week chart */}
      {insights?.by_day?.some(d => d.total > 0) && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h2>When You Spend</h2>
          <div style={{ display: "flex", gap: 6, alignItems: "flex-end", height: 80 }}>
            {insights.by_day.map((d, i) => {
              const max = Math.max(...insights.by_day.map(x => x.total));
              const h = max > 0 ? (d.total / max) * 64 : 0;
              const isPeak = d.total === max && d.total > 0;
              return (
                <div key={i} style={{ flex: 1, textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end" }}>
                  {isPeak && <div style={{ fontSize: 10, color: "var(--accent)", fontWeight: 600, marginBottom: 2 }}>{formatINR(d.total)}</div>}
                  <div style={{
                    width: "100%", maxWidth: 32,
                    background: isPeak ? "var(--accent)" : d.total > 0 ? "var(--bg-input)" : "transparent",
                    height: Math.max(h, 3), borderRadius: 4,
                    border: isPeak ? "none" : d.total > 0 ? "1px solid var(--border)" : "none",
                  }} />
                  <div style={{ fontSize: 11, color: isPeak ? "var(--accent)" : "var(--text-dim)", marginTop: 6, fontWeight: isPeak ? 700 : 400 }}>{d.day}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recent Transactions */}
      {recentTxns.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h2 style={{ marginBottom: 0 }}>Recent Transactions</h2>
            <span onClick={() => navigate("/expenses")} style={{ fontSize: 12, color: "var(--accent)", cursor: "pointer", display: "flex", alignItems: "center", gap: 2 }}>
              View all <ChevronRight size={14} />
            </span>
          </div>
          {recentTxns.map((t) => {
            const isCredit = t.amount < 0;
            const d = new Date(t.date);
            return (
              <div key={t.id} onClick={() => navigate("/expenses")} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "10px 8px", borderRadius: 8, cursor: "pointer",
                borderBottom: "1px solid var(--border)",
              }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {t.description || "Transaction"}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>
                    {d.getDate()} {d.toLocaleString("en-IN", { month: "short" })} · {t.category}
                  </div>
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, flexShrink: 0, marginLeft: 12, color: isCredit ? "var(--green)" : "var(--text)" }}>
                  {isCredit ? "+" : ""}₹{Math.abs(t.amount).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </div>
              </div>
            );
          })}
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

function DashboardInfo() {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position: "relative" }}>
      <Info
        size={16}
        style={{ color: "var(--text-dim)", cursor: "pointer", opacity: 0.5 }}
        onClick={() => setShow(!show)}
      />
      {show && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 99 }} onClick={() => setShow(false)} />
          <div style={{
            position: "absolute", top: "100%", left: 0,
            marginTop: 8, width: 300, padding: 16,
            background: "var(--bg-card)", border: "1px solid var(--border)",
            borderRadius: 10, fontSize: 12, lineHeight: 1.6, color: "var(--text-dim)",
            zIndex: 100, boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
          }}>
            <div style={{ fontWeight: 700, color: "var(--text)", marginBottom: 8, fontSize: 13 }}>How we calculate</div>
            <p style={{ marginBottom: 8 }}><strong style={{ color: "var(--text)" }}>Spent</strong> — All debits excluding self-transfers (CC bill payments, inter-account transfers) to avoid double-counting.</p>
            <p style={{ marginBottom: 8 }}><strong style={{ color: "var(--text)" }}>Salary</strong> — Only payroll/salary credits. Refunds are not income.</p>
            <p style={{ marginBottom: 8 }}><strong style={{ color: "var(--text)" }}>CC Outstanding</strong> — Total charges minus payments, all-time. Not affected by the period filter.</p>
            <p style={{ marginBottom: 0 }}><strong style={{ color: "var(--text)" }}>Categories</strong> — Click any bar to drill into transactions. Tap a category on an expense to re-categorize.</p>
          </div>
        </>
      )}
    </span>
  );
}
