import { useState, useEffect } from "react";
import { Trash2, Search, X, ChevronLeft, ChevronRight } from "lucide-react";
import { getExpenses, addExpense, deleteExpense, updateExpense } from "../api/client";

const CATEGORIES = [
  "food", "transport", "shopping", "entertainment", "bills",
  "health", "education", "groceries", "rent", "emi", "other",
];

const CATEGORY_COLORS = {
  food: "#f97316",
  transport: "#3b82f6",
  shopping: "#8b5cf6",
  entertainment: "#ec4899",
  bills: "#ef4444",
  health: "#22c55e",
  education: "#06b6d4",
  groceries: "#14b8a6",
  rent: "#eab308",
  emi: "#f43f5e",
  other: "#6b7280",
};

const PAYMENT_METHODS = [
  "credit_card", "debit_card", "upi", "cash", "neft", "imps",
];

const BANK_COLORS = {
  hdfc: "#004b87",
  axis: "#97144d",
  scapia: "#6366f1",
  icici: "#f58220",
  sbi: "#22409a",
};

function getSourceInfo(source) {
  if (!source) return { bank: null, type: "unknown", label: "Unknown" };
  const s = source.toLowerCase();
  // Extract bank name
  let bank = null;
  for (const b of ["hdfc", "axis", "scapia", "icici", "sbi", "kotak"]) {
    if (s.includes(b)) { bank = b; break; }
  }
  // Determine source type
  if (s.startsWith("email_")) return { bank, type: "gmail", label: bank ? bank.toUpperCase() + " · Gmail" : "Gmail" };
  if (s.startsWith("stmt_")) return { bank, type: "stmt", label: bank ? bank.toUpperCase() + " · Statement" : "Statement" };
  if (s === "upi_pdf") return { bank: "phonepe", type: "pdf", label: "PhonePe · PDF" };
  if (s === "credit_card_pdf") return { bank, type: "pdf", label: bank ? bank.toUpperCase() + " · PDF" : "CC · PDF" };
  if (s === "bank_pdf") return { bank, type: "pdf", label: bank ? bank.toUpperCase() + " · PDF" : "Bank · PDF" };
  if (s === "manual") return { bank: null, type: "manual", label: "Manual" };
  return { bank, type: "other", label: source };
}

const PAGE_SIZE = 15;

function formatINR(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  const day = d.getDate();
  const month = d.toLocaleString("en-IN", { month: "short" });
  return { day, month };
}

function formatTime(dateStr) {
  const d = new Date(dateStr);
  const h = d.getHours();
  const m = d.getMinutes();
  if (h === 0 && m === 0) return null;
  return d.toLocaleString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true });
}

export default function Expenses() {
  const [allExpenses, setAllExpenses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [page, setPage] = useState(0);
  const [editingId, setEditingId] = useState(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [form, setForm] = useState({
    amount: "",
    category: "other",
    payment_method: "upi",
    description: "",
    date: new Date().toISOString().split("T")[0],
  });
  const [filter, setFilter] = useState({ period: "month" });

  const load = () => {
    const params = { limit: 500 };
    if (filter.period !== "all") params.period = filter.period;
    getExpenses(params).then((data) => {
      setAllExpenses(data);
      setPage(0);
    }).catch(() => {});
  };

  useEffect(load, [filter.period]);

  const filtered = allExpenses.filter((e) => {
    if (categoryFilter && e.category !== categoryFilter) return false;
    if (sourceFilter) {
      if (sourceFilter === "email" && !e.source.startsWith("email")) return false;
      if (sourceFilter === "gmail_stmt" && !e.source.startsWith("stmt_")) return false;
      if (sourceFilter === "pdf" && !e.source.endsWith("_pdf")) return false;
      if (sourceFilter === "manual" && e.source !== "manual") return false;
    }
    if (search) {
      const q = search.toLowerCase();
      return (e.description || "").toLowerCase().includes(q)
        || e.category.includes(q)
        || e.payment_method.includes(q);
    }
    return true;
  });

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const filteredTotal = filtered.reduce((sum, e) => sum + e.amount, 0);

  useEffect(() => setPage(0), [search, categoryFilter, sourceFilter]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.amount || Number(form.amount) <= 0) return;
    await addExpense({ ...form, amount: Number(form.amount), source: "manual" });
    setForm({ amount: "", category: "other", payment_method: "upi", description: "", date: new Date().toISOString().split("T")[0] });
    setShowForm(false);
    load();
  };

  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

  const handleDelete = async (id) => {
    if (deleteConfirmId !== id) {
      setDeleteConfirmId(id);
      setTimeout(() => setDeleteConfirmId(null), 3000); // auto-dismiss after 3s
      return;
    }
    await deleteExpense(id);
    setDeleteConfirmId(null);
    load();
  };

  const handleCategoryChange = async (id, newCategory) => {
    await updateExpense(id, { category: newCategory });
    setAllExpenses((prev) => prev.map((e) => (e.id === id ? { ...e, category: newCategory } : e)));
    setEditingId(null);
  };

  return (
    <div>
      <div className="page-header page-header-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1>Expenses</h1>
          <p>{filtered.length} transactions &middot; {formatINR(filteredTotal)}</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ Add"}
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label>Amount (INR)</label>
                <input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="0.00" required />
              </div>
              <div className="form-group">
                <label>Date</label>
                <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Category</label>
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Payment Method</label>
                <select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
                  {PAYMENT_METHODS.map((p) => <option key={p} value={p}>{p.replace("_", " ")}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Description</label>
              <input type="text" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What was this expense for?" />
            </div>
            <button type="submit" style={{ width: "100%" }}>Add Expense</button>
          </form>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {["week", "month"].map((p) => (
          <button key={p} className={filter.period === p ? "" : "secondary"} onClick={() => setFilter({ ...filter, period: p })}>
            This {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
        <button
          className={filter.period === "all" ? "" : "secondary"}
          onClick={() => setFilter({ ...filter, period: "all" })}
        >
          All Time
        </button>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          style={{ minHeight: 44, padding: "8px 12px", width: "auto", minWidth: 130 }}
        >
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
        </select>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          style={{ minHeight: 44, padding: "8px 12px", width: "auto", minWidth: 110 }}
        >
          <option value="">All Sources</option>
          <option value="email">Gmail Alerts</option>
          <option value="gmail_stmt">Gmail Statements</option>
          <option value="pdf">PDF Upload</option>
          <option value="manual">Manual</option>
        </select>
      </div>

      {/* Search */}
      <div style={{ position: "relative", marginBottom: 16 }}>
        <Search size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-dim)" }} />
        <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search transactions..." style={{ paddingLeft: 36 }} />
        {search && (
          <button onClick={() => setSearch("")} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", padding: 4, minHeight: 0, color: "var(--text-dim)" }}>
            <X size={16} />
          </button>
        )}
      </div>

      {/* Transaction list */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {paged.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>
            {search || categoryFilter ? "No matching transactions." : "No expenses yet. Add one or upload a statement!"}
          </div>
        ) : (
          paged.map((e) => {
            const { day, month } = formatDate(e.date);
            const time = formatTime(e.date);
            const catColor = CATEGORY_COLORS[e.category] || "#6b7280";

            return (
              <div
                key={e.id}
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: "14px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                }}
              >
                {/* Date pill */}
                <div style={{
                  flexShrink: 0, width: 48, textAlign: "center",
                  background: "var(--bg-input)", borderRadius: 10, padding: "8px 4px",
                }}>
                  <div style={{ fontSize: 18, fontWeight: 700, lineHeight: 1 }}>{day}</div>
                  <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>{month}</div>
                </div>

                {/* Middle: description + category */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {e.description || "—"}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                    {editingId === e.id ? (
                      <select
                        value={e.category}
                        onChange={(ev) => handleCategoryChange(e.id, ev.target.value)}
                        onBlur={() => setEditingId(null)}
                        autoFocus
                        style={{ minHeight: 28, padding: "2px 6px", fontSize: 12, width: "auto", borderRadius: 6 }}
                      >
                        {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    ) : (
                      <span
                        onClick={() => setEditingId(e.id)}
                        style={{
                          fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 6,
                          background: catColor + "22", color: catColor, cursor: "pointer",
                          textTransform: "capitalize",
                        }}
                      >
                        {e.category}
                      </span>
                    )}
                    <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                      {e.payment_method.replace("_", " ")}
                    </span>
                    {time && (
                      <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                        {time}
                      </span>
                    )}
                    {(() => {
                      const si = getSourceInfo(e.source);
                      const bankColor = si.bank ? (BANK_COLORS[si.bank] || "#6b7280") : (si.type === "manual" ? "#22c55e" : "#6b7280");
                      return (
                        <span style={{
                          fontSize: 10, padding: "2px 7px", borderRadius: 4, fontWeight: 600,
                          background: bankColor + "22", color: bankColor,
                        }}>
                          {si.label}
                        </span>
                      );
                    })()}
                  </div>
                </div>

                {/* Right: amount + delete */}
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 700 }}>{formatINR(e.amount)}</div>
                  {deleteConfirmId === e.id ? (
                    <button
                      onClick={() => handleDelete(e.id)}
                      className="danger"
                      style={{ padding: "3px 8px", fontSize: 11, minHeight: 0, marginTop: 4 }}
                    >
                      Confirm?
                    </button>
                  ) : (
                    <button
                      onClick={() => handleDelete(e.id)}
                      style={{
                        background: "none", border: "none", color: "var(--text-dim)",
                        padding: 4, minHeight: 0, marginTop: 4, cursor: "pointer",
                        opacity: 0.5, transition: "opacity 0.15s",
                      }}
                      onMouseEnter={(ev) => { ev.currentTarget.style.opacity = 1; ev.currentTarget.style.color = "var(--red)"; }}
                      onMouseLeave={(ev) => { ev.currentTarget.style.opacity = 0.5; ev.currentTarget.style.color = "var(--text-dim)"; }}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination" style={{ marginTop: 16, borderTop: "none" }}>
          <button className="secondary" disabled={page === 0} onClick={() => { setPage(page - 1); window.scrollTo(0, 0); }}>
            <ChevronLeft size={16} />
          </button>
          <span style={{ fontSize: 13, color: "var(--text-dim)" }}>
            {page + 1} of {totalPages}
          </span>
          <button className="secondary" disabled={page >= totalPages - 1} onClick={() => { setPage(page + 1); window.scrollTo(0, 0); }}>
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
