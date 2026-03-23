import { useState, useEffect } from "react";
import { CreditCard, Mail, FileText, PenLine, ChevronRight, ArrowLeft } from "lucide-react";
import { getSources, getExpenses } from "../api/client";

const SOURCE_ICONS = {
  gmail_alert: Mail,
  gmail_statement: FileText,
  pdf_upload: FileText,
  manual: PenLine,
};

const SOURCE_LABELS = {
  gmail_alert: "Gmail Alerts",
  gmail_statement: "Gmail Statements",
  pdf_upload: "PDF Upload",
  manual: "Manual Entry",
};

const BANK_COLORS = {
  HDFC: "#004b87",
  Axis: "#97144d",
  Scapia: "#6366f1",
  ICICI: "#f58220",
  SBI: "#22409a",
  "PhonePe/UPI": "#5f259f",
  Manual: "#22c55e",
};

function formatINR(n) {
  if (n == null) return "₹0";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function formatDate(d) {
  return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function formatTime(dateStr) {
  const d = new Date(dateStr);
  if (d.getHours() === 0 && d.getMinutes() === 0) return null;
  return d.toLocaleString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true });
}

export default function StatementsPage() {
  const [sources, setSources] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSources().then(setSources).catch(() => {});
  }, []);

  const handleViewGroup = async (group) => {
    setSelectedGroup(group);
    setLoading(true);
    try {
      const data = await getExpenses({
        start_date: group.min_date?.split("T")[0],
        end_date: group.max_date?.split("T")[0],
        source: _groupToSourceFilter(group),
        limit: 500,
      });
      // Filter client-side to match the specific bank+month
      const filtered = data.filter((e) => {
        const month = e.date?.substring(0, 7);
        return month === group.month;
      });
      setTransactions(filtered);
    } catch {
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setSelectedGroup(null);
    setTransactions([]);
  };

  // Group sources by bank for the overview
  const bankGroups = {};
  sources.forEach((s) => {
    if (!bankGroups[s.bank]) {
      bankGroups[s.bank] = { bank: s.bank, sources: [], totalAmount: 0, totalTxns: 0 };
    }
    bankGroups[s.bank].sources.push(s);
    bankGroups[s.bank].totalDebits = (bankGroups[s.bank].totalDebits || 0) + (s.total_debits || 0);
    bankGroups[s.bank].totalCredits = (bankGroups[s.bank].totalCredits || 0) + (s.total_credits || 0);
    bankGroups[s.bank].totalPayments = (bankGroups[s.bank].totalPayments || 0) + (s.total_payments || 0);
    bankGroups[s.bank].totalAmount += s.total_amount;
    if (s.is_credit_card) bankGroups[s.bank].isCreditCard = true;
    bankGroups[s.bank].totalTxns += s.transaction_count;
  });

  if (selectedGroup) {
    return (
      <div>
        <div className="page-header">
          <button
            className="secondary"
            onClick={handleBack}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 12, padding: "8px 14px" }}
          >
            <ArrowLeft size={16} /> Back
          </button>
          <h1 style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{
              padding: "4px 12px", borderRadius: 6, fontSize: 14, fontWeight: 700,
              background: (BANK_COLORS[selectedGroup.bank] || "#6b7280") + "22",
              color: BANK_COLORS[selectedGroup.bank] || "#6b7280",
            }}>
              {selectedGroup.bank}
            </span>
            {selectedGroup.month_label}
          </h1>
          <p style={{ color: "var(--text-dim)", marginTop: 4 }}>
            {selectedGroup.transaction_count} transactions · {formatINR(selectedGroup.total_debits || selectedGroup.total_amount)} spent
            {selectedGroup.total_payments > 0 && ` · ${formatINR(selectedGroup.total_payments)} paid`}
            {selectedGroup.total_credits > 0 && <span style={{ color: "var(--green)" }}> · +{formatINR(selectedGroup.total_credits)} received</span>}
            {" · via "}{SOURCE_LABELS[selectedGroup.source_type] || selectedGroup.source_type}
          </p>
        </div>

        {loading ? (
          <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>Loading...</div>
        ) : transactions.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>No transactions found for this period.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {transactions.map((e) => {
              const time = formatTime(e.date);
              return (
                <div key={e.id} style={{
                  background: "var(--bg-card)", border: "1px solid var(--border)",
                  borderRadius: 10, padding: "12px 14px",
                  display: "flex", alignItems: "center", gap: 12,
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {e.description || "—"}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 3, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                      <span>{formatDate(e.date)}</span>
                      {time && <span>{time}</span>}
                      <span style={{
                        padding: "1px 6px", borderRadius: 4, fontSize: 10,
                        background: "rgba(255,255,255,0.06)", textTransform: "capitalize",
                      }}>
                        {e.category}
                      </span>
                      <span style={{ padding: "1px 6px", borderRadius: 4, fontSize: 10, background: "rgba(255,255,255,0.06)" }}>
                        {e.payment_method.replace("_", " ")}
                      </span>
                      {e.reference_id && (
                        <span style={{ fontSize: 10, color: "var(--text-dim)" }}>
                          Ref: {e.reference_id.substring(0, 12)}...
                        </span>
                      )}
                    </div>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 15, flexShrink: 0, color: e.amount < 0 ? (selectedGroup?.is_credit_card ? "var(--accent)" : "var(--green)") : "var(--text)" }}>
                    {e.amount < 0
                      ? (selectedGroup?.is_credit_card
                        ? formatINR(Math.abs(e.amount)) + " ↩"
                        : "+" + formatINR(Math.abs(e.amount)))
                      : formatINR(e.amount)
                    }
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1>Statements & Sources</h1>
        <p>All your imported transaction data, organized by bank and month</p>
      </div>

      {Object.keys(bankGroups).length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>
          No transactions imported yet. Go to Import to get started.
        </div>
      ) : (
        Object.values(bankGroups).map((bg) => {
          const bankColor = BANK_COLORS[bg.bank] || "#6b7280";
          return (
            <div key={bg.bank} className="card" style={{ marginBottom: 16 }}>
              {/* Bank header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 8,
                    background: bankColor + "22", display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <CreditCard size={18} style={{ color: bankColor }} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 16 }}>{bg.bank}</div>
                    <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
                      {bg.totalTxns} txns · {formatINR(bg.totalDebits || 0)} spent
                      {bg.totalPayments > 0 && <span> · {formatINR(bg.totalPayments)} paid</span>}
                      {bg.totalCredits > 0 && <span style={{ color: "var(--green)" }}> · +{formatINR(bg.totalCredits)} received</span>}
                    </div>
                  </div>
                </div>
              </div>

              {/* Monthly breakdowns */}
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {bg.sources.map((s, i) => {
                  const Icon = SOURCE_ICONS[s.source_type] || FileText;
                  return (
                    <div
                      key={i}
                      onClick={() => handleViewGroup(s)}
                      style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "10px 12px", borderRadius: 8, cursor: "pointer",
                        background: "var(--bg-input)", transition: "background 0.15s",
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = "var(--border)"}
                      onMouseLeave={(e) => e.currentTarget.style.background = "var(--bg-input)"}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <Icon size={14} style={{ color: "var(--text-dim)", flexShrink: 0 }} />
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 500 }}>{s.month_label}</div>
                          <div style={{ fontSize: 11, color: "var(--text-dim)" }}>
                            {SOURCE_LABELS[s.source_type] || s.source_type} · {s.transaction_count} txns
                          </div>
                        </div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontWeight: 600, fontSize: 14 }}>
                          {formatINR(s.total_debits || s.total_amount)}
                          {s.total_payments > 0 && <span style={{ fontWeight: 400, fontSize: 11, color: "var(--text-dim)" }}> {formatINR(s.total_payments)} paid</span>}
                          {s.total_credits > 0 && <span style={{ color: "var(--green)", fontWeight: 400, fontSize: 11 }}> +{formatINR(s.total_credits)}</span>}
                        </span>
                        <ChevronRight size={16} style={{ color: "var(--text-dim)" }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

function _groupToSourceFilter(group) {
  // Map source_type back to source field prefix for API filtering
  if (group.source_type === "gmail_alert") return "email_" + group.bank.toLowerCase();
  if (group.source_type === "gmail_statement") return "stmt_" + group.bank.toLowerCase();
  if (group.source_type === "pdf_upload") return group.bank === "PhonePe/UPI" ? "upi_pdf" : "credit_card_pdf";
  return "manual";
}
