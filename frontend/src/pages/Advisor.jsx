import { useState } from "react";
import { ShoppingCart, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { canIBuy } from "../api/client";

const CATEGORIES = [
  "", "food", "transport", "shopping", "entertainment", "bills",
  "health", "education", "groceries", "rent", "emi", "other",
];

function formatINR(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function Advisor() {
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [verdict, setVerdict] = useState(null);

  const handleCheck = async (e) => {
    e.preventDefault();
    if (!amount || Number(amount) <= 0) return;
    setLoading(true);
    try {
      const res = await canIBuy(Number(amount), category || null);
      setVerdict(res);
    } catch {
      setVerdict(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Can I Buy This?</h1>
        <p>Check if a purchase fits your budget before spending</p>
      </div>

      <div className="card">
        <form onSubmit={handleCheck}>
          <div className="form-group">
            <label>How much does it cost?</label>
            <input
              type="number"
              className="amount-input"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="₹ 2,000"
              required
            />
          </div>
          <div className="form-group">
            <label>Category (optional — for category budget check)</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">Any / Not sure</option>
              {CATEGORIES.filter(Boolean).map((c) => (
                <option key={c} value={c}>{c.replace("_", " ")}</option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={loading} style={{ width: "100%", padding: 14, fontSize: 16 }}>
            <ShoppingCart size={18} style={{ marginRight: 8, verticalAlign: "middle" }} />
            {loading ? "Analyzing..." : "Can I Buy This?"}
          </button>
        </form>
      </div>

      {verdict && (
        <div className={`verdict ${verdict.can_buy ? "can-buy" : "cannot-buy"}`}>
          <h3>
            {verdict.can_buy ? (
              <>
                <CheckCircle size={24} style={{ marginRight: 8, verticalAlign: "middle" }} />
                Yes, you can buy this! ({formatINR(verdict.amount)})
              </>
            ) : (
              <>
                <XCircle size={24} style={{ marginRight: 8, verticalAlign: "middle" }} />
                Not recommended ({formatINR(verdict.amount)})
              </>
            )}
          </h3>

          {verdict.reasons.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <strong>Analysis:</strong>
              <ul>
                {verdict.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {verdict.warnings.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ color: "var(--yellow)" }}>
                <AlertTriangle size={16} style={{ marginRight: 4, verticalAlign: "middle" }} />
                Warnings:
              </strong>
              <ul>
                {verdict.warnings.map((w, i) => (
                  <li key={i} style={{ color: "var(--yellow)" }}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {verdict.can_buy && (
            <div style={{ marginBottom: 12 }}>
              <strong>After purchase:</strong>
              <ul>
                <li>Weekly remaining: {formatINR(verdict.weekly_remaining_after)}</li>
                <li>Monthly remaining: {formatINR(verdict.monthly_remaining_after)}</li>
              </ul>
            </div>
          )}

          <div className="suggestion">
            <strong>Suggestion:</strong> {verdict.suggestion}
          </div>
        </div>
      )}
    </div>
  );
}
