import { useState, useEffect } from "react";
import { CreditCard, Landmark, Mail, FileText, PenLine, ChevronRight, ChevronDown, ChevronUp, ArrowLeft, Info } from "lucide-react";
import { getSources, getExpenses, getNetworth, detectCards } from "../api/client";

const BANK_COLORS = {
  HDFC: "#004b87", Axis: "#97144d", Scapia: "#6366f1",
  ICICI: "#f58220", SBI: "#22409a", KOTAK: "#ed1c24",
  "PhonePe/UPI": "#5f259f", Manual: "#22c55e",
};

const SOURCE_LABELS = {
  gmail_alert: "Gmail Alerts", gmail_statement: "Gmail Statements",
  pdf_upload: "PDF Upload", manual: "Manual Entry",
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
  const [networth, setNetworth] = useState(null);
  const [selectedCard, setSelectedCard] = useState(null); // bank+accountType key
  const [selectedMonth, setSelectedMonth] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [txnLoading, setTxnLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      getSources().then(setSources),
      getNetworth().then(setNetworth),
      detectCards().catch(() => {}), // auto-detect cards on first visit
    ]).catch(() => {}).finally(() => setLoading(false));
  }, []);

  // Build card groups
  const cards = {};
  sources.forEach((s) => {
    const key = `${s.bank}_${s.account_type}`;
    if (!cards[key]) {
      cards[key] = {
        bank: s.bank, accountType: s.account_type, isCreditCard: s.is_credit_card,
        months: [], totalDebits: 0, totalPayments: 0, totalCredits: 0, totalTxns: 0,
      };
    }
    cards[key].months.push(s);
    cards[key].totalDebits += (s.total_debits || 0);
    cards[key].totalPayments += (s.total_payments || 0);
    cards[key].totalCredits += (s.total_credits || 0);
    cards[key].totalTxns += s.transaction_count;
  });

  // Get current month spend per card
  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  const handleViewMonth = async (monthData) => {
    setSelectedMonth(monthData);
    setTxnLoading(true);
    try {
      const [year, month] = monthData.month.split("-");
      const lastDay = new Date(parseInt(year), parseInt(month), 0).getDate();
      const params = {
        start_date: `${monthData.month}-01`,
        end_date: `${monthData.month}-${lastDay}`,
        limit: 500,
      };
      // If source_filter available, use it; otherwise fetch all for this period
      const sf = _groupToSourceFilter(monthData);
      if (sf) params.source = sf;
      const data = await getExpenses(params);
      setTransactions(data);
    } catch { setTransactions([]); }
    finally { setTxnLoading(false); }
  };

  if (loading) {
    return (
      <div>
        <div className="page-header"><h1>Cards & Accounts</h1></div>
        <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>Loading...</div>
      </div>
    );
  }

  // Transaction drill-down view
  if (selectedMonth) {
    return (
      <div>
        <div className="page-header">
          <button className="secondary" onClick={() => { setSelectedMonth(null); setTransactions([]); }}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 12, padding: "8px 14px" }}>
            <ArrowLeft size={16} /> Back
          </button>
          <h1>{selectedMonth.bank} · {selectedMonth.month_label}</h1>
          <p style={{ color: "var(--text-dim)", marginTop: 4 }}>
            {selectedMonth.transaction_count} transactions · {formatINR(selectedMonth.total_debits)} spent
            {selectedMonth.total_payments > 0 && ` · ${formatINR(selectedMonth.total_payments)} paid`}
            {selectedMonth.total_credits > 0 && <span style={{ color: "var(--green)" }}> · +{formatINR(selectedMonth.total_credits)}</span>}
          </p>
        </div>
        {txnLoading ? (
          <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>Loading...</div>
        ) : transactions.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>No transactions found.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {transactions.map((e) => {
              const time = formatTime(e.date);
              return (
                <div key={e.id} style={{
                  background: "var(--bg-card)", border: "1px solid var(--border)",
                  borderRadius: 10, padding: "12px 14px", display: "flex", alignItems: "center", gap: 12,
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {e.description || "—"}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 3, display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span>{formatDate(e.date)}</span>
                      {time && <span>{time}</span>}
                      <span style={{ padding: "1px 5px", borderRadius: 3, fontSize: 10, background: "rgba(255,255,255,0.06)", textTransform: "capitalize" }}>{e.category}</span>
                    </div>
                  </div>
                  <div style={{
                    fontWeight: 700, fontSize: 14, flexShrink: 0,
                    color: e.amount < 0 ? (selectedMonth.is_credit_card ? "var(--accent)" : "var(--green)") : "var(--text)",
                  }}>
                    {e.amount < 0
                      ? (selectedMonth.is_credit_card ? formatINR(Math.abs(e.amount)) + " ↩" : "+" + formatINR(Math.abs(e.amount)))
                      : formatINR(e.amount)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // Main card view
  const cardList = Object.values(cards);
  const ccCards = cardList.filter(c => c.isCreditCard);
  const bankCards = cardList.filter(c => !c.isCreditCard);

  return (
    <div>
      <div className="page-header">
        <h1>Cards & Accounts</h1>
        <p style={{ color: "var(--text-dim)", marginTop: 4 }}>
          {ccCards.length} credit card{ccCards.length !== 1 ? "s" : ""} · {bankCards.length} bank account{bankCards.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Credit Cards */}
      {ccCards.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>Credit Cards</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {ccCards.map((card) => {
              const color = BANK_COLORS[card.bank] || "#6b7280";
              const outstanding = networth?.cc_outstanding?.[card.bank];
              const thisMonthData = card.months.find(m => m.month === currentMonth);
              const lastPayment = card.months
                .filter(m => (m.total_payments || 0) > 0)
                .sort((a, b) => b.month.localeCompare(a.month))[0];
              const key = `${card.bank}_${card.accountType}`;
              const expanded = selectedCard === key;

              return (
                <div key={key} style={{
                  background: "var(--bg-card)", border: "1px solid var(--border)",
                  borderRadius: 14, overflow: "hidden",
                }}>
                  {/* Card header — colored top bar */}
                  <div style={{ background: color + "15", borderBottom: "1px solid var(--border)", padding: "16px 18px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <CreditCard size={18} style={{ color }} />
                          <span style={{ fontSize: 16, fontWeight: 700 }}>{card.bank}</span>
                          <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: color + "22", color }}>Credit Card</span>
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
                          {card.totalTxns} transactions across {card.months.length} months
                        </div>
                      </div>
                      {outstanding && (
                        <div style={{ textAlign: "right" }}>
                          <div style={{ fontSize: 20, fontWeight: 700, color: outstanding.outstanding > 0 ? "var(--red)" : "var(--green)" }}>
                            {outstanding.outstanding > 0 ? formatINR(outstanding.outstanding) : "Paid up"}
                          </div>
                          <div style={{ fontSize: 10, color: "var(--text-dim)" }}>outstanding</div>
                        </div>
                      )}
                    </div>

                    {/* Quick stats */}
                    <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
                      {thisMonthData && (
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600 }}>{formatINR(thisMonthData.total_debits)}</div>
                          <div style={{ fontSize: 10, color: "var(--text-dim)" }}>This month</div>
                        </div>
                      )}
                      {outstanding && outstanding.charges > 0 && (
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600 }}>{formatINR(outstanding.charges)}</div>
                          <div style={{ fontSize: 10, color: "var(--text-dim)" }}>Total charged</div>
                        </div>
                      )}
                      {outstanding && outstanding.payments > 0 && (
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600 }}>{formatINR(outstanding.payments)}</div>
                          <div style={{ fontSize: 10, color: "var(--text-dim)" }}>Total paid</div>
                        </div>
                      )}
                      {lastPayment && (
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600 }}>{formatINR(lastPayment.total_payments)}</div>
                          <div style={{ fontSize: 10, color: "var(--text-dim)" }}>Last payment ({lastPayment.month_label})</div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Monthly breakdown — collapsible */}
                  <div style={{ padding: "0 18px" }}>
                    <button
                      onClick={() => setSelectedCard(expanded ? null : key)}
                      style={{ width: "100%", background: "none", border: "none", color: "var(--text-dim)", padding: "10px 0",
                        display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12 }}
                    >
                      <span>Monthly breakdown</span>
                      {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {expanded && (
                      <div style={{ paddingBottom: 14 }}>
                        {card.months.sort((a, b) => b.month.localeCompare(a.month)).map((m, i) => (
                          <div key={i} onClick={() => handleViewMonth(m)}
                            style={{
                              display: "flex", justifyContent: "space-between", alignItems: "center",
                              padding: "8px 10px", borderRadius: 8, cursor: "pointer", marginBottom: 4,
                              background: "var(--bg-input)", transition: "background 0.15s",
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.background = "var(--border)"}
                            onMouseLeave={(e) => e.currentTarget.style.background = "var(--bg-input)"}
                          >
                            <div>
                              <span style={{ fontSize: 13, fontWeight: 500 }}>{m.month_label}</span>
                              <span style={{ fontSize: 11, color: "var(--text-dim)", marginLeft: 8 }}>{m.transaction_count} txns</span>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <span style={{ fontSize: 13, fontWeight: 600 }}>{formatINR(m.total_debits)}</span>
                              {m.total_payments > 0 && <span style={{ fontSize: 11, color: "var(--text-dim)" }}>{formatINR(m.total_payments)} paid</span>}
                              <ChevronRight size={14} style={{ color: "var(--text-dim)" }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bank Accounts */}
      {bankCards.length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>Bank Accounts</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {bankCards.map((card) => {
              const color = BANK_COLORS[card.bank] || "#6b7280";
              const thisMonthData = card.months.find(m => m.month === currentMonth);
              const key = `${card.bank}_${card.accountType}`;
              const expanded = selectedCard === key;

              return (
                <div key={key} style={{
                  background: "var(--bg-card)", border: "1px solid var(--border)",
                  borderRadius: 14, overflow: "hidden",
                }}>
                  <div style={{ background: color + "08", borderBottom: "1px solid var(--border)", padding: "14px 18px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <Landmark size={18} style={{ color }} />
                      <span style={{ fontSize: 16, fontWeight: 700 }}>{card.bank}</span>
                      <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: "var(--green-bg)", color: "var(--green)" }}>Bank Account</span>
                    </div>

                    <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap" }}>
                      {thisMonthData && (
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600 }}>{formatINR(thisMonthData.total_debits)}</div>
                          <div style={{ fontSize: 10, color: "var(--text-dim)" }}>This month spent</div>
                        </div>
                      )}
                      {card.totalCredits > 0 && (
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--green)" }}>+{formatINR(card.totalCredits)}</div>
                          <div style={{ fontSize: 10, color: "var(--text-dim)" }}>Total received</div>
                        </div>
                      )}
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600 }}>{card.totalTxns}</div>
                        <div style={{ fontSize: 10, color: "var(--text-dim)" }}>Total transactions</div>
                      </div>
                    </div>
                  </div>

                  {/* Monthly breakdown */}
                  <div style={{ padding: "0 18px" }}>
                    <button
                      onClick={() => setSelectedCard(expanded ? null : key)}
                      style={{ width: "100%", background: "none", border: "none", color: "var(--text-dim)", padding: "10px 0",
                        display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12 }}
                    >
                      <span>{card.months.length} months of data</span>
                      {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {expanded && (
                      <div style={{ paddingBottom: 14 }}>
                        {card.months.sort((a, b) => b.month.localeCompare(a.month)).map((m, i) => (
                          <div key={i} onClick={() => handleViewMonth(m)}
                            style={{
                              display: "flex", justifyContent: "space-between", alignItems: "center",
                              padding: "8px 10px", borderRadius: 8, cursor: "pointer", marginBottom: 4,
                              background: "var(--bg-input)", transition: "background 0.15s",
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.background = "var(--border)"}
                            onMouseLeave={(e) => e.currentTarget.style.background = "var(--bg-input)"}
                          >
                            <div>
                              <span style={{ fontSize: 13, fontWeight: 500 }}>{m.month_label}</span>
                              <span style={{ fontSize: 11, color: "var(--text-dim)", marginLeft: 8 }}>{m.transaction_count} txns</span>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <span style={{ fontSize: 13, fontWeight: 600 }}>{formatINR(m.total_debits)}</span>
                              {m.total_credits > 0 && <span style={{ fontSize: 11, color: "var(--green)" }}>+{formatINR(m.total_credits)}</span>}
                              <ChevronRight size={14} style={{ color: "var(--text-dim)" }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {Object.keys(cards).length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>
          No cards or accounts detected yet. Import transactions to get started.
        </div>
      )}
    </div>
  );
}

function _groupToSourceFilter(group) {
  if (group.source_filter) return group.source_filter;
  if (group.source_type === "mixed" || !group.source_type) return "";
  return "";
}
