import { useState, useEffect } from "react";
import { getBudget, setBudget, getBudgetStatus } from "../api/client";

const CATEGORIES = [
  "food", "transport", "shopping", "entertainment", "bills",
  "health", "education", "groceries", "rent", "emi",
];

function formatINR(n) {
  if (n == null) return "₹0";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function getColor(pct) {
  if (pct > 100) return "var(--red)";
  if (pct > 75) return "var(--yellow)";
  return "var(--green)";
}

export default function BudgetPage() {
  const [budget, setBudgetState] = useState(null);
  const [status, setStatus] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    monthly_limit: "",
    weekly_limit: "",
    category_limits: [],
  });

  const load = () => {
    getBudget().then((b) => {
      setBudgetState(b);
      if (b) {
        setForm({
          monthly_limit: b.monthly_limit,
          weekly_limit: b.weekly_limit,
          category_limits: b.category_limits || [],
        });
      }
    }).catch(() => {});
    getBudgetStatus().then(setStatus).catch(() => {});
  };

  useEffect(load, []);

  const handleSave = async (e) => {
    e.preventDefault();
    await setBudget({
      monthly_limit: Number(form.monthly_limit),
      weekly_limit: Number(form.weekly_limit),
      category_limits: form.category_limits.filter(
        (cl) => cl.category && cl.limit_amount > 0
      ),
    });
    setEditing(false);
    load();
  };

  const addCategoryLimit = () => {
    setForm({
      ...form,
      category_limits: [
        ...form.category_limits,
        { category: CATEGORIES[0], limit_amount: 0 },
      ],
    });
  };

  const updateCatLimit = (idx, field, value) => {
    const updated = [...form.category_limits];
    updated[idx] = { ...updated[idx], [field]: field === "limit_amount" ? Number(value) : value };
    setForm({ ...form, category_limits: updated });
  };

  const removeCatLimit = (idx) => {
    setForm({
      ...form,
      category_limits: form.category_limits.filter((_, i) => i !== idx),
    });
  };

  return (
    <div>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1>Budget</h1>
          <p>Set spending limits to stay on track</p>
        </div>
        <button onClick={() => setEditing(!editing)}>
          {editing ? "Cancel" : budget ? "Edit Budget" : "Set Budget"}
        </button>
      </div>

      {editing && (
        <div className="card" style={{ marginBottom: 24 }}>
          <form onSubmit={handleSave}>
            <div className="form-row">
              <div className="form-group">
                <label>Monthly Limit (INR)</label>
                <input
                  type="number"
                  value={form.monthly_limit}
                  onChange={(e) => setForm({ ...form, monthly_limit: e.target.value })}
                  placeholder="30000"
                  required
                />
              </div>
              <div className="form-group">
                <label>Weekly Limit (INR)</label>
                <input
                  type="number"
                  value={form.weekly_limit}
                  onChange={(e) => setForm({ ...form, weekly_limit: e.target.value })}
                  placeholder="7500"
                  required
                />
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, color: "var(--text-dim)", fontWeight: 500 }}>
                Category Limits (optional)
              </label>
              {form.category_limits.map((cl, idx) => (
                <div key={idx} style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <select
                    value={cl.category}
                    onChange={(e) => updateCatLimit(idx, "category", e.target.value)}
                    style={{ flex: 1 }}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <input
                    type="number"
                    value={cl.limit_amount}
                    onChange={(e) => updateCatLimit(idx, "limit_amount", e.target.value)}
                    placeholder="Limit"
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="danger"
                    onClick={() => removeCatLimit(idx)}
                    style={{ padding: "8px 12px" }}
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="secondary"
                onClick={addCategoryLimit}
                style={{ marginTop: 8 }}
              >
                + Add Category Limit
              </button>
            </div>

            <button type="submit">Save Budget</button>
          </form>
        </div>
      )}

      {/* Budget Status */}
      {status && (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="label">Weekly</div>
              <div className="value" style={{ color: getColor(status.weekly_percent) }}>
                {formatINR(status.weekly_remaining)}
              </div>
              <div className="sub">
                {formatINR(status.weekly_spent)} spent of {formatINR(status.weekly_limit)}
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${Math.min(status.weekly_percent, 100)}%`,
                    background: getColor(status.weekly_percent),
                  }}
                />
              </div>
            </div>
            <div className="stat-card">
              <div className="label">Monthly</div>
              <div className="value" style={{ color: getColor(status.monthly_percent) }}>
                {formatINR(status.monthly_remaining)}
              </div>
              <div className="sub">
                {formatINR(status.monthly_spent)} spent of {formatINR(status.monthly_limit)}
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${Math.min(status.monthly_percent, 100)}%`,
                    background: getColor(status.monthly_percent),
                  }}
                />
              </div>
            </div>
          </div>

          {Object.keys(status.categories).length > 0 && (
            <div className="card">
              <h2>Category Budgets</h2>
              <table>
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>Spent</th>
                    <th>Limit</th>
                    <th>Remaining</th>
                    <th>Usage</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(status.categories).map(([cat, info]) => (
                    <tr key={cat}>
                      <td>{cat}</td>
                      <td>{formatINR(info.spent)}</td>
                      <td>{formatINR(info.limit)}</td>
                      <td style={{ color: getColor(info.percent_used) }}>
                        {formatINR(info.remaining)}
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div className="progress-bar" style={{ flex: 1, margin: 0 }}>
                            <div
                              className="progress-fill"
                              style={{
                                width: `${Math.min(info.percent_used, 100)}%`,
                                background: getColor(info.percent_used),
                              }}
                            />
                          </div>
                          <span style={{ fontSize: 12, color: getColor(info.percent_used) }}>
                            {info.percent_used}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {!status && !editing && (
        <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>
          <p>No budget set yet. Click "Set Budget" to get started.</p>
        </div>
      )}
    </div>
  );
}
