import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Trash2, Search, X, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, Plus, CreditCard, Smartphone, Filter, Receipt } from "lucide-react";
import { getExpenses, addExpense, deleteExpense, updateExpense, getCards, linkCardPayment, unlinkCardPayment, applyCategoryToSimilar, getExcludedBanks, getTransferMatches, linkTransfer, unlinkTransfer } from "../api/client";

const CATEGORIES = [
  "food", "transport", "shopping", "entertainment", "bills",
  "subscriptions", "health", "education", "groceries", "rent",
  "home", "personal care", "investment", "emi", "transfer",
  "lent", "borrowed", "atm", "salary", "other",
];

const CATEGORY_META = {
  food:          { color: "#f97316", icon: "🍔", label: "Food" },
  transport:     { color: "#3b82f6", icon: "🚗", label: "Transport" },
  shopping:      { color: "#8b5cf6", icon: "🛍️", label: "Shopping" },
  entertainment: { color: "#ec4899", icon: "🎬", label: "Entertainment" },
  bills:         { color: "#ef4444", icon: "📄", label: "Bills" },
  subscriptions: { color: "#0ea5e9", icon: "🔄", label: "Subscriptions" },
  health:        { color: "#22c55e", icon: "💊", label: "Health" },
  education:     { color: "#06b6d4", icon: "📚", label: "Education" },
  groceries:     { color: "#14b8a6", icon: "🥬", label: "Groceries" },
  rent:          { color: "#eab308", icon: "🏠", label: "Rent" },
  home:          { color: "#a3866a", icon: "🔧", label: "Home" },
  "personal care": { color: "#d946ef", icon: "💇", label: "Personal Care" },
  investment:    { color: "#059669", icon: "📈", label: "Investment" },
  emi:           { color: "#f43f5e", icon: "🏦", label: "Loan & EMI" },
  transfer:      { color: "#64748b", icon: "↔️", label: "Self Transfer" },
  lent:          { color: "#f472b6", icon: "🤝", label: "Lent (Owed to me)" },
  borrowed:      { color: "#fb923c", icon: "🙏", label: "Borrowed (I owe)" },
  atm:           { color: "#a855f7", icon: "🏧", label: "ATM" },
  salary:        { color: "#10b981", icon: "💰", label: "Salary" },
  other:         { color: "#6b7280", icon: "📌", label: "Other" },
};

const CATEGORY_COLORS = Object.fromEntries(Object.entries(CATEGORY_META).map(([k, v]) => [k, v.color]));

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
  for (const b of ["hdfc", "axis", "scapia", "icici", "sbi", "kotak", "karnataka", "canara", "bob", "pnb", "idfc", "yes_bank", "indusind"]) {
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
  const navigate = useNavigate();
  const navState = location.state || {};

  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [allExpenses, setAllExpenses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [page, setPage] = useState(0);
  const [editingId, setEditingId] = useState(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [selectedExpenseId, setSelectedExpenseId] = useState(null);
  const [cards, setCards] = useState([]);
  const [linkingId, setLinkingId] = useState(null); // expense id being linked to a card
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("date_desc");
  const [categoryFilter, setCategoryFilter] = useState(navState.category || "");
  const [bankFilter, setBankFilter] = useState(navState.bank || "");
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

  const [excludedBanks, setExcludedBanks] = useState([]);

  useEffect(load, [selectedYear, selectedMonth, weekOffset, mode]);
  useEffect(() => {
    getCards().then(setCards).catch(() => {});
    getExcludedBanks().then((d) => setExcludedBanks(d.banks || [])).catch(() => {});
  }, []);

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

  // Client-side filters — exclude hidden banks first
  const visibleExpenses = excludedBanks.length > 0
    ? allExpenses.filter((e) => !excludedBanks.includes(getSourceInfo(e.source).bank))
    : allExpenses;

  const availableBanks = [...new Set(visibleExpenses.map((e) => getSourceInfo(e.source).bank).filter(Boolean))];

  const filtered = visibleExpenses.filter((e) => {
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

  // Sort
  const sorted = [...filtered].sort((a, b) => {
    switch (sortBy) {
      case "date_asc": return new Date(a.date) - new Date(b.date);
      case "amount_desc": return Math.abs(b.amount) - Math.abs(a.amount);
      case "amount_asc": return Math.abs(a.amount) - Math.abs(b.amount);
      default: return new Date(b.date) - new Date(a.date); // date_desc
    }
  });

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const spentTotal = filtered.reduce((s, e) => s + (e.amount > 0 ? e.amount : 0), 0);
  const receivedTotal = Math.abs(filtered.reduce((s, e) => s + (e.amount < 0 ? e.amount : 0), 0));

  useEffect(() => setPage(0), [search, categoryFilter, bankFilter, txnTypeFilter, sortBy]);

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

  const handleLinkCard = async (expenseId, cardId) => {
    await linkCardPayment(expenseId, cardId);
    setAllExpenses((prev) => prev.map((e) => e.id === expenseId ? { ...e, category: "transfer", card_id: cardId } : e));
    setLinkingId(null);
  };

  const handleUnlinkCard = async (expenseId) => {
    await unlinkCardPayment(expenseId);
    setAllExpenses((prev) => prev.map((e) => e.id === expenseId ? { ...e, card_id: null } : e));
    setLinkingId(null);
  };

  const hasActiveFilters = categoryFilter || bankFilter || txnTypeFilter || search;
  const activeFilterCount = [categoryFilter, bankFilter, txnTypeFilter, search].filter(Boolean).length;

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

      {/* Collapsible Filters */}
      <div style={{ marginBottom: 10 }}>
        <button
          className="secondary"
          onClick={() => setFiltersOpen(!filtersOpen)}
          style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", fontSize: 13, minHeight: 36 }}
        >
          <Filter size={14} /> Filters
          {activeFilterCount > 0 && (
            <span style={{
              background: "var(--accent)", color: "#fff", fontSize: 10, fontWeight: 700,
              width: 18, height: 18, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
            }}>{activeFilterCount}</span>
          )}
          {filtersOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {filtersOpen && (
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
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
                <option value="debit">Debits (spent)</option>
                <option value="credit">Credits (refunds/salary)</option>
              </select>
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} style={{ padding: "6px 10px", fontSize: 12, minHeight: 34, width: "auto", minWidth: 0, flex: "0 1 auto" }}>
                <option value="date_desc">Newest first</option>
                <option value="date_asc">Oldest first</option>
                <option value="amount_desc">Highest amount</option>
                <option value="amount_asc">Lowest amount</option>
              </select>
              {hasActiveFilters && (
                <button className="secondary" onClick={() => { setCategoryFilter(""); setBankFilter(""); setTxnTypeFilter(""); setSearch(""); setSortBy("date_desc"); }} style={{ padding: "4px 10px", fontSize: 11, minHeight: 34 }}>
                  Clear
                </button>
              )}
            </div>
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-dim)" }} />
              <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." style={{ paddingLeft: 34, fontSize: 13, minHeight: 36 }} />
              {search && (
                <button onClick={() => setSearch("")} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", padding: 4, minHeight: 0, color: "var(--text-dim)" }}>
                  <X size={14} />
                </button>
              )}
            </div>
          </div>
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
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1,2,3,4,5].map(i => (
            <div key={i} className="loading-skeleton" style={{ height: 64, borderRadius: 10 }} />
          ))}
        </div>
      ) : (
      <>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {paged.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: 48 }}>
            {hasActiveFilters ? (
              <span style={{ color: "var(--text-dim)" }}>No matching transactions.</span>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                <Receipt size={40} style={{ color: "var(--text-dim)", opacity: 0.5 }} />
                <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text)" }}>No transactions yet</div>
                <p style={{ color: "var(--text-dim)", fontSize: 13, maxWidth: 300, lineHeight: 1.5 }}>
                  Import your transactions from SMS, Gmail, or PDF statements. Go to Account → Import Data to get started.
                </p>
                <button onClick={() => navigate("/upload")} style={{ padding: "10px 20px", fontSize: 14, display: "flex", alignItems: "center", gap: 6 }}>
                  Import Data
                </button>
              </div>
            )}
          </div>
        ) : (
          paged.map((e) => {
            const { day, month } = formatDate(e.date);
            const time = formatTime(e.date);
            const catColor = CATEGORY_COLORS[e.category] || "#6b7280";
            const si = getSourceInfo(e.source);
            const bankColor = si.bank ? (BANK_COLORS[si.bank] || "#6b7280") : (si.type === "manual" ? "#22c55e" : "#6b7280");

            return (
              <div key={e.id} onClick={() => setSelectedExpenseId(e.id)} style={{
                background: "var(--bg-card)", border: "1px solid var(--border)",
                borderRadius: 12, padding: "12px 14px", display: "flex", alignItems: "center", gap: 12,
                cursor: "pointer", WebkitTapHighlightColor: "transparent",
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
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: "1px 6px", borderRadius: 4,
                      background: catColor + "22", color: catColor, textTransform: "capitalize",
                    }}>{CATEGORY_META[e.category]?.label || e.category}</span>
                    <span style={{ fontSize: 10, color: "var(--text-dim)" }}>{e.payment_method.replace("_", " ")}</span>
                    {time && <span style={{ fontSize: 10, color: "var(--text-dim)" }}>{time}</span>}
                    <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 3, fontWeight: 600, background: bankColor + "22", color: bankColor }}>{si.label}</span>
                  </div>
                </div>

                <div style={{ textAlign: "right", flexShrink: 0, display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: e.amount < 0 ? "var(--green)" : "var(--text)" }}>
                    {e.amount < 0 ? "+" + formatINR(Math.abs(e.amount)) : formatINR(e.amount)}
                  </div>
                  <ChevronRight size={14} style={{ color: "var(--text-dim)", opacity: 0.4 }} />
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

      {/* Transaction Detail Modal */}
      {selectedExpenseId && (() => {
        const exp = allExpenses.find(e => e.id === selectedExpenseId);
        if (!exp) return null;
        return <TransactionDetail
          expense={exp}
          cards={cards}
          allExpenses={visibleExpenses}
          onClose={() => { setSelectedExpenseId(null); load(); }}
          onCategoryChange={(cat) => { handleCategoryChange(exp.id, cat); setAllExpenses(prev => prev.map(e => e.id === exp.id ? { ...e, category: cat } : e)); }}
          onLinkCard={() => { setSelectedExpenseId(null); setLinkingId(exp.id); }}
          onDelete={() => { handleDelete(exp.id); setSelectedExpenseId(null); }}
          onApplyToSimilar={async (expId, cat) => {
            const res = await applyCategoryToSimilar(expId, cat);
            load();
            return res;
          }}
          onRefresh={() => { setSelectedExpenseId(null); load(); }}
        />;
      })()}

      {/* Card Payment Modal */}
      {linkingId && <CardPaymentModal
        expense={allExpenses.find(e => e.id === linkingId)}
        cards={cards.filter(c => c.card_type === "credit_card")}
        onLink={(cardId) => handleLinkCard(linkingId, cardId)}
        onClose={() => setLinkingId(null)}
      />}
    </div>
  );
}

function CardPaymentModal({ expense, cards, onLink, onClose }) {
  if (!expense) { onClose(); return null; }

  return (
    <>
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 200 }} onClick={onClose} />
      <div style={{
        position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 201,
        background: "var(--bg-card)", borderRadius: "16px 16px 0 0",
        padding: "24px 20px", paddingBottom: "max(24px, env(safe-area-inset-bottom))",
        maxHeight: "60vh", overflowY: "auto",
      }}>
        <div style={{ width: 40, height: 4, background: "var(--border)", borderRadius: 2, margin: "0 auto 16px" }} />
        <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Mark as Card Payment</h3>
        <p style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 16 }}>
          This will exclude it from spending and link it to the selected credit card's outstanding balance.
        </p>

        <div style={{
          background: "var(--bg-input)", borderRadius: 10, padding: "12px 14px", marginBottom: 16,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{expense.description || "—"}</div>
            <div style={{ fontSize: 11, color: "var(--text-dim)" }}>{new Date(expense.date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</div>
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, flexShrink: 0, marginLeft: 8 }}>
            {"₹" + Number(expense.amount).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          </div>
        </div>

        <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Which card was this payment for?
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {cards.length === 0 ? (
            <p style={{ color: "var(--text-dim)", fontSize: 13, textAlign: "center", padding: 16 }}>
              No credit cards detected yet. Import a credit card statement first.
            </p>
          ) : cards.map((c) => (
            <button key={c.id} onClick={() => onLink(c.id)}
              style={{
                width: "100%", padding: "14px 16px", fontSize: 14,
                display: "flex", alignItems: "center", gap: 10, justifyContent: "flex-start",
                background: "var(--bg-input)", border: "1px solid var(--border)",
                borderRadius: 10, cursor: "pointer", color: "var(--text)",
              }}>
              <CreditCard size={18} style={{ color: "var(--accent)" }} />
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600 }}>{c.bank_name} {c.nickname || "Credit Card"}</div>
                {c.last_four && <div style={{ fontSize: 11, color: "var(--text-dim)" }}>•••• {c.last_four}</div>}
              </div>
            </button>
          ))}
        </div>

        <button className="secondary" onClick={onClose}
          style={{ width: "100%", marginTop: 12, padding: "12px" }}>
          Cancel
        </button>
      </div>
    </>
  );
}

function TransactionDetail({ expense, cards, allExpenses, onClose, onCategoryChange, onLinkCard, onDelete, onApplyToSimilar, onRefresh }) {
  const [editCat, setEditCat] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showApplyAll, setShowApplyAll] = useState(false);
  const [applyResult, setApplyResult] = useState(null);
  const [pendingCategory, setPendingCategory] = useState(null);
  const [showTransferMatch, setShowTransferMatch] = useState(false);
  const [transferMatches, setTransferMatches] = useState([]);
  const [matchLoading, setMatchLoading] = useState(false);
  const [unlinking, setUnlinking] = useState(false);
  const e = expense;
  const si = getSourceInfo(e.source);
  const bankColor = si.bank ? (BANK_COLORS[si.bank] || "#6b7280") : "#6b7280";
  const catColor = CATEGORY_COLORS[e.category] || "#6b7280";
  const time = formatTime(e.date);
  const fullDate = new Date(e.date).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const isCredit = e.amount < 0;
  const ccCards = cards.filter(c => c.card_type === "credit_card");

  return (
    <>
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 200 }} onClick={onClose} />
      <div style={{
        position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 201,
        background: "var(--bg-card)", borderRadius: "16px 16px 0 0",
        padding: "20px", paddingBottom: "max(20px, env(safe-area-inset-bottom))",
        maxHeight: "80vh", overflowY: "auto",
      }}>
        <div style={{ width: 40, height: 4, background: "var(--border)", borderRadius: 2, margin: "0 auto 20px" }} />

        {/* Amount */}
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <div style={{ fontSize: 32, fontWeight: 700, color: isCredit ? "var(--green)" : "var(--text)" }}>
            {isCredit ? "+" : ""}{"₹" + Number(Math.abs(e.amount)).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-dim)", marginTop: 4 }}>{isCredit ? "Credit / Refund" : "Debit"}</div>
        </div>

        {/* Description */}
        <div style={{ background: "var(--bg-input)", borderRadius: 10, padding: "14px 16px", marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Description</div>
          <div style={{ fontSize: 15, fontWeight: 500, wordBreak: "break-word" }}>{e.description || "No description"}</div>
        </div>

        {/* Details grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
          <div style={{ background: "var(--bg-input)", borderRadius: 10, padding: "12px 14px" }}>
            <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Date</div>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 2 }}>{fullDate}</div>
            {time && <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{time}</div>}
          </div>
          <div style={{ background: "var(--bg-input)", borderRadius: 10, padding: "12px 14px" }}>
            <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Payment</div>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 2, textTransform: "capitalize" }}>{e.payment_method.replace("_", " ")}</div>
          </div>
          <div style={{ background: "var(--bg-input)", borderRadius: 10, padding: "12px 14px" }}>
            <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Source</div>
            <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 3, fontWeight: 600, background: bankColor + "22", color: bankColor, marginTop: 2, display: "inline-block" }}>{si.label}</span>
          </div>
          <div style={{ background: "var(--bg-input)", borderRadius: 10, padding: "12px 14px", cursor: "pointer" }} onClick={() => setEditCat(true)}>
            <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Category</div>
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 2 }}>
              <span style={{ fontSize: 14 }}>{CATEGORY_META[e.category]?.icon || "📌"}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: catColor, textTransform: "capitalize" }}>{CATEGORY_META[e.category]?.label || e.category}</span>
              <span style={{ fontSize: 10, color: "var(--text-dim)" }}>edit</span>
            </div>
          </div>
        </div>

        {/* Original SMS message */}
        {e.reference_id?.startsWith("sms:") && (
          <div style={{ background: "rgba(14,165,233,0.1)", border: "1px solid rgba(14,165,233,0.3)", borderRadius: 10, padding: "10px 14px", marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: "#0ea5e9", display: "flex", alignItems: "center", gap: 4 }}>
              <Smartphone size={12} /> Original SMS
            </div>
            <div style={{ fontSize: 12, marginTop: 4, wordBreak: "break-word", lineHeight: 1.5, color: "var(--text-dim)" }}>
              {e.reference_id.substring(4)}
            </div>
          </div>
        )}

        {/* Reference ID (non-SMS) */}
        {e.reference_id && !e.reference_id.startsWith("sms:") && (
          <div style={{ background: "var(--bg-input)", borderRadius: 10, padding: "10px 14px", marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Reference ID</div>
            <div style={{ fontSize: 12, fontFamily: "monospace", marginTop: 2, wordBreak: "break-all" }}>{e.reference_id}</div>
          </div>
        )}

        {/* Category picker grid */}
        {editCat && (
          <div style={{
            background: "var(--bg-input)", borderRadius: 10, padding: "14px",
            marginBottom: 12,
          }}>
            <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Select Category
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
              {CATEGORIES.map((c) => {
                const meta = CATEGORY_META[c] || { color: "#6b7280", icon: "📌", label: c };
                const isActive = e.category === c;
                return (
                  <button key={c} onClick={async () => {
                    if (c !== e.category) {
                      if (c === "transfer" && !e.linked_transaction_id) {
                        // Show transfer match popup before applying
                        setEditCat(false);
                        setMatchLoading(true);
                        setShowTransferMatch(true);
                        try {
                          const matches = await getTransferMatches(e.id);
                          setTransferMatches(matches);
                        } catch { setTransferMatches([]); }
                        setMatchLoading(false);
                        return;
                      }
                      onCategoryChange(c);
                      setPendingCategory(c);
                      setShowApplyAll(true);
                    }
                    setEditCat(false);
                  }} style={{
                    padding: "10px 6px", borderRadius: 8, border: isActive ? `2px solid ${meta.color}` : "1px solid var(--border)",
                    background: isActive ? meta.color + "22" : "var(--bg-card)",
                    display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
                    cursor: "pointer", minHeight: 0,
                    color: isActive ? meta.color : "var(--text)",
                  }}>
                    <span style={{ fontSize: 18 }}>{meta.icon}</span>
                    <span style={{ fontSize: 10, fontWeight: isActive ? 700 : 500, textTransform: "capitalize" }}>{meta.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Apply to all similar */}
        {showApplyAll && pendingCategory && !applyResult && (
          <div style={{
            background: "rgba(99,102,241,0.1)", border: "1px solid var(--accent)",
            borderRadius: 10, padding: "12px 14px", marginBottom: 12,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              Apply "{pendingCategory}" to all similar transactions?
            </div>
            <p style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 10 }}>
              This will update all transactions with a similar description and remember for future imports.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={async () => {
                const res = await onApplyToSimilar(e.id, pendingCategory);
                setApplyResult(res);
                setShowApplyAll(false);
              }} style={{ flex: 1, fontSize: 13, padding: "10px" }}>
                Apply to All ({pendingCategory})
              </button>
              <button className="secondary" onClick={() => setShowApplyAll(false)} style={{ padding: "10px 14px", fontSize: 13 }}>
                Just This One
              </button>
            </div>
          </div>
        )}
        {applyResult && (
          <div style={{
            background: "var(--green-bg)", border: "1px solid var(--green)",
            borderRadius: 10, padding: "10px 14px", marginBottom: 12, fontSize: 13, color: "var(--green)",
          }}>
            Updated {applyResult.updated} similar transactions to "{applyResult.category}"
          </div>
        )}

        {/* Self-Transfer Match Popup */}
        {showTransferMatch && (
          <div style={{
            background: "rgba(99,102,241,0.1)", border: "1px solid var(--accent)",
            borderRadius: 10, padding: "14px", marginBottom: 12,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
              Link matching transaction?
            </div>
            <p style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 10 }}>
              Select the opposite transaction from another bank, or skip to just mark as self transfer.
            </p>
            {matchLoading ? (
              <div style={{ textAlign: "center", padding: 16, color: "var(--text-dim)", fontSize: 13 }}>Finding matches...</div>
            ) : transferMatches.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
                {transferMatches.map((m) => {
                  const mSi = getSourceInfo(m.source);
                  const mDate = new Date(m.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
                  return (
                    <button key={m.id} onClick={async () => {
                      try {
                        await linkTransfer(e.id, m.id);
                        setShowTransferMatch(false);
                        if (onRefresh) onRefresh();
                      } catch {}
                    }} style={{
                      padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)",
                      background: "var(--bg-card)", display: "flex", justifyContent: "space-between",
                      alignItems: "center", cursor: "pointer", textAlign: "left", minHeight: 0,
                    }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: m.amount < 0 ? "var(--green)" : "var(--text)" }}>
                          {m.amount < 0 ? "+" : ""}{"₹" + Math.abs(m.amount).toLocaleString("en-IN")}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>
                          {(m.description || "").substring(0, 40)} {mDate}
                        </div>
                      </div>
                      <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "var(--bg-input)", color: "var(--text-dim)", fontWeight: 600 }}>
                        {mSi.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: 12, color: "var(--text-dim)", fontSize: 12 }}>No matching transactions found nearby.</div>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button onClick={() => {
                onCategoryChange("transfer");
                setShowTransferMatch(false);
                setPendingCategory("transfer");
                setShowApplyAll(true);
              }} className="secondary" style={{ flex: 1, fontSize: 12, padding: "10px" }}>
                Skip — Just Mark as Self Transfer
              </button>
              <button onClick={() => setShowTransferMatch(false)} className="secondary" style={{ padding: "10px 14px", fontSize: 12 }}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Linked Self-Transfer */}
        {e.linked_transaction_id && (() => {
          const linked = allExpenses?.find(x => x.id === e.linked_transaction_id);
          const linkedSi = linked ? getSourceInfo(linked.source) : null;
          return (
            <div style={{
              background: "rgba(100,116,139,0.1)", border: "1px solid rgba(100,116,139,0.3)",
              borderRadius: 10, padding: "10px 14px", marginBottom: 12,
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-dim)", display: "flex", alignItems: "center", gap: 4 }}>
                  ↔️ Linked Self Transfer
                </div>
                {linked ? (
                  <div style={{ fontSize: 12, marginTop: 4, color: "var(--text)" }}>
                    {linked.amount < 0 ? "+" : ""}₹{Math.abs(linked.amount).toLocaleString("en-IN")} from {linkedSi?.label || "unknown"}
                    {" · "}{new Date(linked.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, marginTop: 4, color: "var(--text-dim)" }}>Linked to #{e.linked_transaction_id}</div>
                )}
              </div>
              <button onClick={async () => {
                setUnlinking(true);
                try {
                  await unlinkTransfer(e.id);
                  if (onRefresh) onRefresh();
                } catch {}
                setUnlinking(false);
              }} disabled={unlinking} className="secondary" style={{ padding: "6px 10px", fontSize: 11, minHeight: 0 }}>
                {unlinking ? "..." : "Unlink"}
              </button>
            </div>
          );
        })()}

        {/* Actions */}
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          {ccCards.length > 0 && e.amount > 0 && e.category !== "transfer" && (
            <button onClick={onLinkCard} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "12px" }}>
              <CreditCard size={16} /> Card Payment
            </button>
          )}
          {confirmDelete ? (
            <button className="danger" onClick={onDelete} style={{ flex: 1, padding: "12px" }}>Confirm Delete</button>
          ) : (
            <button className="secondary" onClick={() => setConfirmDelete(true)} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "12px" }}>
              <Trash2 size={14} /> Delete
            </button>
          )}
        </div>
        <button className="secondary" onClick={onClose} style={{ width: "100%", marginTop: 8, padding: "10px" }}>Close</button>
      </div>
    </>
  );
}
