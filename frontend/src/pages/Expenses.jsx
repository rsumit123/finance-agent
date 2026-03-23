import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Trash2, Search, X, ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { getExpenses, addExpense, deleteExpense, updateExpense } from "../api/client";

const CATEGORIES = [
  "food", "transport", "shopping", "entertainment", "bills",
  "health", "education", "groceries", "rent", "emi", "transfer",
  "atm", "salary", "other",
];

const CATEGORY_COLORS = {
  food: "#f97316", transport: "#3b82f6", shopping: "#8b5cf6",
  entertainment: "#ec4899", bills: "#ef4444", health: "#22c55e",
  education: "#06b6d4", groceries: "#14b8a6", rent: "#eab308",
  emi: "#f43f5e", transfer: "#64748b", atm: "#a855f7",
  salary: "#10b981", other: "#6b7280",
};

const BANK_COLORS = {
  hdfc: "#004b87", axis: "#97144d", scapia: "#6366f1",
  icici: "#f58220", sbi: "#22409a",
};

const PAYMENT_METHODS = [
  "credit_card", "debit_card", "upi", "cash", "neft", "imps",
];

const PAGE_SIZE = 15;

function formatINR(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return { day: d.getDate(), month: d.toLocaleString("en-IN", { month: "short" }) };
}

function formatTime(dateStr) {
  const d = new Date(dateStr);
  if (d.getHours() === 0 && d.getMinutes() === 0) return null;
  return d.toLocaleString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true });
}

function getSourceInfo(source) {
  if (!source) return { bank: null, type: "unknown", label: "Unknown" };
  const s = source.toLowerCase();
  let bank = null;
  for (const b of ["hdfc", "axis", "scapia", "icici", "sbi", "kotak"]) {
    if (s.includes(b)) { bank = b; break; }
  }
  if (s.startsWith("email_")) return { bank, type: "gmail", label: bank ? bank.toUpperCase() + " · Gmail" : "Gmail" };
  if (s.includes("_cc")) return { bank, type: "stmt", label: bank ? bank.toUpperCase() + " · CC" : "CC" };
  if (s.includes("_bank")) return { bank, type: "stmt", label: bank ? bank.toUpperCase() + " · Bank" : "Bank" };
  if (s.startsWith("stmt_")) return { bank, type: "stmt", label: bank ? bank.toUpperCase() + " · Statement" : "Statement" };
  if (s === "upi_pdf") return { bank: "phonepe", type: "pdf", label: "PhonePe · PDF" };
  if (s === "credit_card_pdf") return { bank, type: "pdf", label: "CC · PDF" };
  if (s === "manual") return { bank: null, type: "manual", label: "Manual" };
  return { bank, type: "other", label: source };
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
  start.setDate(now.getDate() - now.getDay() + 1 + offset * 7);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return { start: start.toISOString().split("T")[0], end: end.toISOString().split("T")[0] };
}

function formatMonthLabel(year, month) {
  return new Date(year, month - 1).toLocaleString("en-IN", { month: "long", year: "numeric" });
}

function formatWeekLabel(startStr) {
  const s = new Date(startStr);
  const e = new Date(s); e.setDate(s.getDate() + 6);
  return `${s.getDate()} ${s.toLocaleString("en-IN", { month: "short" })} — ${e.getDate()} ${e.toLocaleString("en-IN", { month: "short" })}`;
}

export default function Expenses() {
  const location = useLocation();
  const navState = location.state || {};

  const [loading, setLoading] = useState(true);
  const [allExpenses, setAllExpenses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [page, setPage] = useState(0);
  const [editingId, setEditingId] = useState(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState(navState.category || "");
  const [bankFilter, setBankFilter] = useState("");
  const [txnTypeFilter, setTxnTypeFilter] = useState(navState.txnType || "");
  const [form, setForm] = useState({
    amount: "", category: "other", payment_method: "upi",
    description: "", date: new Date().toISOString().split("T")[0],
  });

  // Period state — initialized from nav state if coming from Dashboard
  const now = new Date();
  const [mode, setMode] = useState(navState.mode || "month");
  const [selectedYear, setSelectedYear] = useState(navState.year || now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(navState.month || now.getMonth() + 1);
  const [weekOffset, setWeekOffset] = useState(navState.weekOffset || 0);

  const dateRange = mode === "month"
    ? getMonthRange(selectedYear, selectedMonth)
    : getWeekRange(weekOffset);

  const periodLabel = mode === "month"
    ? formatMonthLabel(selectedYear, selectedMonth)
    : formatWeekLabel(dateRange.start);

  const isCurrentPeriod = mode === "month"
    ? (selectedYear === now.getFullYear() && selectedMonth === now.getMonth() + 1)
    : weekOffset === 0;

  const load = () => {
    setLoading(true);
    getExpenses({ start_date: dateRange.start, end_date: dateRange.end, limit: 500 })
      .then((data) => { setAllExpenses(data); setPage(0); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, [selectedYear, selectedMonth, weekOffset, mode]);

  const goBack = () => {
    if (mode === "month") {
      if (selectedMonth === 1) { setSelectedMonth(12); setSelectedYear(selectedYear - 1); }
      else setSelectedMonth(selectedMonth - 1);
    } else setWeekOffset(weekOffset - 1);
  };

  const goForward = () => {
    if (isCurrentPeriod) return;
    if (mode === "month") {
      if (selectedMonth === 12) { setSelectedMonth(1); setSelectedYear(selectedYear + 1); }
      else setSelectedMonth(selectedMonth + 1);
    } else setWeekOffset(weekOffset + 1);
  };

  const goToNow = () => {
    setSelectedYear(now.getFullYear()); setSelectedMonth(now.getMonth() + 1); setWeekOffset(0);
  };

  // Client-side filters
  const availableBanks = [...new Set(allExpenses.map((e) => getSourceInfo(e.source).bank).filter(Boolean))];

  const filtered = allExpenses.filter((e) => {
    if (categoryFilter && e.category !== categoryFilter) return false;
    if (bankFilter && getSourceInfo(e.source).bank !== bankFilter) return false;
    if (txnTypeFilter === "debit" && e.amount < 0) return false;
    if (txnTypeFilter === "credit" && e.amount >= 0) return false;
    if (search) {
      const q = search.toLowerCase();
      return (e.description || "").toLowerCase().includes(q) || e.category.includes(q) || e.payment_method.includes(q);
    }
    return true;
  });

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const spentTotal = filtered.reduce((s, e) => s + (e.amount > 0 ? e.amount : 0), 0);
  const receivedTotal = Math.abs(filtered.reduce((s, e) => s + (e.amount < 0 ? e.amount : 0), 0));

  useEffect(() => setPage(0), [search, categoryFilter, bankFilter, txnTypeFilter]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.amount || Number(form.amount) <= 0) return;
    await addExpense({ ...form, amount: Number(form.amount), source: "manual" });
    setForm({ amount: "", category: "other", payment_method: "upi", description: "", date: new Date().toISOString().split("T")[0] });
    setShowForm(false);
    load();
  };

  const handleDelete = async (id) => {
    if (deleteConfirmId !== id) { setDeleteConfirmId(id); setTimeout(() => setDeleteConfirmId(null), 3000); return; }
    await deleteExpense(id); setDeleteConfirmId(null); load();
  };

  const handleCategoryChange = async (id, newCat) => {
    await updateExpense(id, { category: newCat });
    setAllExpenses((prev) => prev.map((e) => e.id === id ? { ...e, category: newCat } : e));
    setEditingId(null);
  };

  const hasActiveFilters = categoryFilter || bankFilter || txnTypeFilter || search;

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Expenses</h1>
        <button onClick={() => setShowForm(!showForm)} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {showForm ? <X size={16} /> : <Plus size={16} />}
          {showForm ? "Cancel" : "Add"}
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 16 }}>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group"><label>Amount</label><input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="0.00" required /></div>
              <div className="form-group"><label>Date</label><input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></div>
            </div>
            <div className="form-row">
              <div className="form-group"><label>Category</label><select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}</select></div>
              <div className="form-group"><label>Payment</label><select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>{PAYMENT_METHODS.map((p) => <option key={p} value={p}>{p.replace("_", " ")}</option>)}</select></div>
            </div>
            <div className="form-group"><label>Description</label><input type="text" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What was this for?" /></div>
            <button type="submit" style={{ width: "100%" }}>Add Expense</button>
          </form>
        </div>
      )}

      {/* Period picker — same design as Dashboard */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "var(--bg-card)", border: "1px solid var(--border)",
        borderRadius: 10, padding: "8px 12px", marginBottom: 12, flexWrap: "wrap", gap: 8,
      }}>
        <div style={{ display: "flex", gap: 4 }}>
          <button className={mode === "week" ? "" : "secondary"} onClick={() => setMode("week")} style={{ padding: "6px 12px", fontSize: 12, minHeight: 32 }}>Weekly</button>
          <button className={mode === "month" ? "" : "secondary"} onClick={() => setMode("month")} style={{ padding: "6px 12px", fontSize: 12, minHeight: 32 }}>Monthly</button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button className="secondary" onClick={goBack} style={{ padding: "4px 8px", minHeight: 32 }}><ChevronLeft size={16} /></button>
          <span style={{ fontSize: 14, fontWeight: 600, minWidth: 140, textAlign: "center" }}>{periodLabel}</span>
          <button className="secondary" onClick={goForward} disabled={isCurrentPeriod} style={{ padding: "4px 8px", minHeight: 32 }}><ChevronRight size={16} /></button>
        </div>
        {!isCurrentPeriod && <button className="secondary" onClick={goToNow} style={{ padding: "4px 10px", fontSize: 11, minHeight: 32 }}>Today</button>}
      </div>

      {/* Filters row */}
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} style={{ padding: "6px 10px", fontSize: 12, minHeight: 34, width: "auto", minWidth: 0, flex: "0 1 auto" }}>
          <option value="">Category</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {availableBanks.length > 0 && (
          <select value={bankFilter} onChange={(e) => setBankFilter(e.target.value)} style={{ padding: "6px 10px", fontSize: 12, minHeight: 34, width: "auto", minWidth: 0, flex: "0 1 auto" }}>
            <option value="">Bank</option>
            {availableBanks.map((b) => <option key={b} value={b}>{b.charAt(0).toUpperCase() + b.slice(1)}</option>)}
          </select>
        )}
        <select value={txnTypeFilter} onChange={(e) => setTxnTypeFilter(e.target.value)} style={{ padding: "6px 10px", fontSize: 12, minHeight: 34, width: "auto", minWidth: 0, flex: "0 1 auto" }}>
          <option value="">Type</option>
          <option value="debit">Expenses</option>
          <option value="credit">Income</option>
        </select>
        {hasActiveFilters && (
          <button className="secondary" onClick={() => { setCategoryFilter(""); setBankFilter(""); setTxnTypeFilter(""); setSearch(""); }} style={{ padding: "4px 10px", fontSize: 11, minHeight: 34 }}>
            Clear
          </button>
        )}
      </div>

      {/* Search */}
      <div style={{ position: "relative", marginBottom: 12 }}>
        <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-dim)" }} />
        <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." style={{ paddingLeft: 34, fontSize: 13, minHeight: 36 }} />
        {search && (
          <button onClick={() => setSearch("")} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", padding: 4, minHeight: 0, color: "var(--text-dim)" }}>
            <X size={14} />
          </button>
        )}
      </div>

      {/* Summary bar */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-dim)", marginBottom: 10, padding: "0 2px" }}>
        <span>
          {filtered.length} transactions · {formatINR(spentTotal)} spent
          {receivedTotal > 0 && <span style={{ color: "var(--green)" }}> · +{formatINR(receivedTotal)}</span>}
        </span>
        {totalPages > 1 && <span>Page {page + 1}/{totalPages}</span>}
      </div>

      {/* Transaction list */}
      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>Loading...</div>
      ) : (
      <>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {paged.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>
            {hasActiveFilters ? "No matching transactions." : "No expenses for this period."}
          </div>
        ) : (
          paged.map((e) => {
            const { day, month } = formatDate(e.date);
            const time = formatTime(e.date);
            const catColor = CATEGORY_COLORS[e.category] || "#6b7280";
            const si = getSourceInfo(e.source);
            const bankColor = si.bank ? (BANK_COLORS[si.bank] || "#6b7280") : (si.type === "manual" ? "#22c55e" : "#6b7280");

            return (
              <div key={e.id} style={{
                background: "var(--bg-card)", border: "1px solid var(--border)",
                borderRadius: 12, padding: "12px 14px", display: "flex", alignItems: "center", gap: 12,
              }}>
                <div style={{ flexShrink: 0, width: 44, textAlign: "center", background: "var(--bg-input)", borderRadius: 8, padding: "6px 4px" }}>
                  <div style={{ fontSize: 16, fontWeight: 700, lineHeight: 1 }}>{day}</div>
                  <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 1 }}>{month}</div>
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {e.description || "—"}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 3, flexWrap: "wrap" }}>
                    {editingId === e.id ? (
                      <select value={e.category} onChange={(ev) => handleCategoryChange(e.id, ev.target.value)} onBlur={() => setEditingId(null)} autoFocus
                        style={{ minHeight: 24, padding: "1px 4px", fontSize: 11, width: "auto", borderRadius: 4 }}>
                        {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    ) : (
                      <span onClick={() => setEditingId(e.id)} style={{
                        fontSize: 10, fontWeight: 600, padding: "1px 6px", borderRadius: 4, cursor: "pointer",
                        background: catColor + "22", color: catColor, textTransform: "capitalize",
                      }}>{e.category}</span>
                    )}
                    <span style={{ fontSize: 10, color: "var(--text-dim)" }}>{e.payment_method.replace("_", " ")}</span>
                    {time && <span style={{ fontSize: 10, color: "var(--text-dim)" }}>{time}</span>}
                    <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 3, fontWeight: 600, background: bankColor + "22", color: bankColor }}>{si.label}</span>
                  </div>
                </div>

                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: e.amount < 0 ? "var(--green)" : "var(--text)" }}>
                    {e.amount < 0 ? "+" + formatINR(Math.abs(e.amount)) : formatINR(e.amount)}
                  </div>
                  {deleteConfirmId === e.id ? (
                    <button onClick={() => handleDelete(e.id)} className="danger" style={{ padding: "2px 6px", fontSize: 10, minHeight: 0, marginTop: 2 }}>Delete?</button>
                  ) : (
                    <button onClick={() => handleDelete(e.id)} style={{
                      background: "none", border: "none", color: "var(--text-dim)", padding: 2, minHeight: 0, marginTop: 2, cursor: "pointer", opacity: 0.4,
                    }} title="Delete"><Trash2 size={12} /></button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {totalPages > 1 && (
        <div className="pagination" style={{ marginTop: 12, borderTop: "none" }}>
          <button className="secondary" disabled={page === 0} onClick={() => { setPage(page - 1); window.scrollTo(0, 0); }}><ChevronLeft size={16} /></button>
          <span style={{ fontSize: 13, color: "var(--text-dim)" }}>{page + 1} of {totalPages}</span>
          <button className="secondary" disabled={page >= totalPages - 1} onClick={() => { setPage(page + 1); window.scrollTo(0, 0); }}><ChevronRight size={16} /></button>
        </div>
      )}
      </>
      )}
    </div>
  );
}
