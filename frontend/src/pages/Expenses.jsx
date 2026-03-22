import { useState, useEffect } from "react";
import { Trash2, Search, X } from "lucide-react";
import { getExpenses, addExpense, deleteExpense, updateExpense } from "../api/client";

const CATEGORIES = [
  "food", "transport", "shopping", "entertainment", "bills",
  "health", "education", "groceries", "rent", "emi", "other",
];

const PAYMENT_METHODS = [
  "credit_card", "debit_card", "upi", "cash", "neft", "imps",
];

const PAGE_SIZE = 15;

function formatINR(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function Expenses() {
  const [allExpenses, setAllExpenses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [page, setPage] = useState(0);
  const [editingId, setEditingId] = useState(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [form, setForm] = useState({
    amount: "",
    category: "other",
    payment_method: "upi",
    description: "",
    date: new Date().toISOString().split("T")[0],
  });
  const [filter, setFilter] = useState({ period: "month" });

  const load = () => {
    getExpenses({ period: filter.period, limit: 500 }).then((data) => {
      setAllExpenses(data);
      setPage(0);
    }).catch(() => {});
  };

  useEffect(load, [filter.period]);

  // Client-side filtering
  const filtered = allExpenses.filter((e) => {
    if (categoryFilter && e.category !== categoryFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      const match = (e.description || "").toLowerCase().includes(q)
        || e.category.toLowerCase().includes(q)
        || e.payment_method.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const pageTotal = paged.reduce((sum, e) => sum + e.amount, 0);

  // Reset page when filters change
  useEffect(() => setPage(0), [search, categoryFilter]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.amount || Number(form.amount) <= 0) return;
    await addExpense({ ...form, amount: Number(form.amount), source: "manual" });
    setForm({
      amount: "",
      category: "other",
      payment_method: "upi",
      description: "",
      date: new Date().toISOString().split("T")[0],
    });
    setShowForm(false);
    load();
  };

  const handleDelete = async (id) => {
    await deleteExpense(id);
    load();
  };

  const handleCategoryChange = async (id, newCategory) => {
    await updateExpense(id, { category: newCategory });
    setAllExpenses((prev) =>
      prev.map((e) => (e.id === id ? { ...e, category: newCategory } : e))
    );
    setEditingId(null);
  };

  return (
    <div>
      <div className="page-header page-header-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1>Expenses</h1>
          <p>{filtered.length} transactions this {filter.period}</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ Add"}
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 24 }}>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label>Amount (INR)</label>
                <input
                  type="number"
                  step="0.01"
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  placeholder="0.00"
                  required
                />
              </div>
              <div className="form-group">
                <label>Date</label>
                <input
                  type="date"
                  value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })}
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Category</label>
                <select
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c.replace("_", " ")}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Payment Method</label>
                <select
                  value={form.payment_method}
                  onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
                >
                  {PAYMENT_METHODS.map((p) => (
                    <option key={p} value={p}>{p.replace("_", " ")}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Description</label>
              <input
                type="text"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="What was this expense for?"
              />
            </div>
            <button type="submit" style={{ width: "100%" }}>Add Expense</button>
          </form>
        </div>
      )}

      {/* Filters bar */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {["week", "month"].map((p) => (
          <button
            key={p}
            className={filter.period === p ? "" : "secondary"}
            onClick={() => setFilter({ ...filter, period: p })}
          >
            This {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          style={{ minHeight: 44, padding: "8px 12px", flex: "0 0 auto", width: "auto", minWidth: 120 }}
        >
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.replace("_", " ")}</option>
          ))}
        </select>
      </div>

      {/* Search */}
      <div style={{ position: "relative", marginBottom: 16 }}>
        <Search size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-dim)" }} />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search transactions..."
          style={{ paddingLeft: 36 }}
        />
        {search && (
          <button
            onClick={() => setSearch("")}
            style={{
              position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
              background: "none", border: "none", padding: 4, minHeight: 0, color: "var(--text-dim)"
            }}
          >
            <X size={16} />
          </button>
        )}
      </div>

      <div className="card">
        {/* Page summary */}
        {paged.length > 0 && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, fontSize: 13, color: "var(--text-dim)" }}>
            <span>{formatINR(pageTotal)} on this page</span>
            <span style={{ fontSize: 11 }}>Tap category to edit</span>
          </div>
        )}

        <table className="responsive-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Category</th>
              <th>Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {paged.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", color: "var(--text-dim)", padding: 32 }}>
                  {search || categoryFilter
                    ? "No matching transactions found."
                    : "No expenses found. Add one or upload a statement!"}
                </td>
              </tr>
            ) : (
              paged.map((e) => (
                <tr key={e.id}>
                  <td data-label="Date">{e.date}</td>
                  <td data-label="Description" style={{ wordBreak: "break-word" }}>{e.description || "—"}</td>
                  <td data-label="Category">
                    {editingId === e.id ? (
                      <select
                        value={e.category}
                        onChange={(ev) => handleCategoryChange(e.id, ev.target.value)}
                        onBlur={() => setEditingId(null)}
                        autoFocus
                        style={{ minHeight: 32, padding: "4px 8px", fontSize: 12, width: "auto" }}
                      >
                        {CATEGORIES.map((c) => (
                          <option key={c} value={c}>{c.replace("_", " ")}</option>
                        ))}
                      </select>
                    ) : (
                      <span
                        className="tag default"
                        onClick={() => setEditingId(e.id)}
                        style={{ cursor: "pointer" }}
                        title="Click to change category"
                      >
                        {e.category}
                      </span>
                    )}
                    {" "}
                    <span className="tag default">{e.payment_method.replace("_", " ")}</span>
                  </td>
                  <td data-label="Amount" style={{ fontWeight: 600 }}>{formatINR(e.amount)}</td>
                  <td data-label="">
                    <button
                      className="danger"
                      style={{ padding: "6px 10px", minHeight: 0 }}
                      onClick={() => handleDelete(e.id)}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div className="pagination">
            <button
              className="secondary"
              disabled={page === 0}
              onClick={() => { setPage(page - 1); window.scrollTo(0, 0); }}
            >
              Prev
            </button>
            <span>{page + 1} / {totalPages}</span>
            <button
              className="secondary"
              disabled={page >= totalPages - 1}
              onClick={() => { setPage(page + 1); window.scrollTo(0, 0); }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
