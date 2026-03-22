import { useState, useEffect } from "react";
import { Trash2 } from "lucide-react";
import { getExpenses, addExpense, deleteExpense } from "../api/client";

const CATEGORIES = [
  "food", "transport", "shopping", "entertainment", "bills",
  "health", "education", "groceries", "rent", "emi", "other",
];

const PAYMENT_METHODS = [
  "credit_card", "debit_card", "upi", "cash", "neft", "imps",
];

function formatINR(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function Expenses() {
  const [expenses, setExpenses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    amount: "",
    category: "other",
    payment_method: "upi",
    description: "",
    date: new Date().toISOString().split("T")[0],
  });
  const [filter, setFilter] = useState({ period: "month" });

  const load = () => {
    getExpenses({ period: filter.period }).then(setExpenses).catch(() => {});
  };

  useEffect(load, [filter.period]);

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

  return (
    <div>
      <div className="page-header page-header-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1>Expenses</h1>
          <p>Track and manage your spending</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ Add Expense"}
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
            <button type="submit">Add Expense</button>
          </form>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {["week", "month"].map((p) => (
          <button
            key={p}
            className={filter.period === p ? "" : "secondary"}
            onClick={() => setFilter({ ...filter, period: p })}
          >
            This {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>

      <div className="card">
        <table className="responsive-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Category</th>
              <th>Payment</th>
              <th>Source</th>
              <th style={{ textAlign: "right" }}>Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {expenses.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", color: "var(--text-dim)", padding: 32 }}>
                  No expenses found. Add one or upload a statement!
                </td>
              </tr>
            ) : (
              expenses.map((e) => (
                <tr key={e.id}>
                  <td data-label="Date">{e.date}</td>
                  <td data-label="Description">{e.description || "—"}</td>
                  <td data-label="Category"><span className="tag default">{e.category}</span></td>
                  <td data-label="Payment"><span className="tag default">{e.payment_method.replace("_", " ")}</span></td>
                  <td data-label="Source"><span className="tag default">{e.source}</span></td>
                  <td data-label="Amount" style={{ fontWeight: 600 }}>{formatINR(e.amount)}</td>
                  <td data-label="">
                    <button
                      className="danger"
                      style={{ padding: "4px 8px" }}
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
      </div>
    </div>
  );
}
