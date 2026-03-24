import { useState, useRef, useEffect } from "react";
import { Upload, FileText, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, Mail, RefreshCw, Unlink, Key, Trash2, AlertOctagon, X, AlertCircle, Calendar, Loader } from "lucide-react";
import { uploadStatement, getUploadHistory, getGmailStatus, getGmailAuthUrl, startGmailSync, getSyncStatus, getLatestSync, disconnectGmail, getPasswords, addPassword, deletePassword, clearAllData } from "../api/client";

function formatINR(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function UploadPage() {
  // PDF upload state
  const [file, setFile] = useState(null);
  const [fileType, setFileType] = useState("auto");
  const [password, setPassword] = useState("");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);
  const [dragover, setDragover] = useState(false);
  const [showDuplicates, setShowDuplicates] = useState(false);
  const inputRef = useRef();

  // Gmail state
  const [gmailStatus, setGmailStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncJobId, setSyncJobId] = useState(null);
  const [syncResult, setSyncResult] = useState(null);
  const [syncAfter, setSyncAfter] = useState("");
  const [syncBefore, setSyncBefore] = useState("");

  // Password state
  const [passwords, setPasswords] = useState([]);
  const [newPwLabel, setNewPwLabel] = useState("");
  const [newPwValue, setNewPwValue] = useState("");
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const refreshAll = () => {
    getUploadHistory().then(setHistory).catch(() => {});
    getGmailStatus().then(setGmailStatus).catch(() => {});
    getPasswords().then(setPasswords).catch(() => {});
    // Load last sync result
    getLatestSync().then((job) => {
      if (job?.status === "completed" && job.result) setSyncResult(job.result);
      if (job?.status === "running" || job?.status === "pending") {
        setSyncing(true);
        setSyncJobId(job.job_id);
      }
    }).catch(() => {});
  };

  useEffect(refreshAll, []);

  // Poll for sync job status
  useEffect(() => {
    if (!syncJobId || !syncing) return;
    const interval = setInterval(async () => {
      try {
        const job = await getSyncStatus(syncJobId);
        if (job.status === "completed") {
          setSyncing(false);
          setSyncResult(job.result);
          setSyncJobId(null);
          refreshAll();
        } else if (job.status === "failed") {
          setSyncing(false);
          setSyncResult({ error: job.error || "Sync failed" });
          setSyncJobId(null);
        }
      } catch {
        // Keep polling
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [syncJobId, syncing]);

  // Handlers
  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const res = await uploadStatement(file, fileType, password);
      setResult(res);
      setFile(null);
      refreshAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed. Check your PDF.");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragover(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile?.name.toLowerCase().endsWith(".pdf")) setFile(droppedFile);
  };

  const handleConnectGmail = async () => {
    try {
      const { auth_url } = await getGmailAuthUrl();
      window.location.href = auth_url;
    } catch {
      setError("Failed to start Gmail connection.");
    }
  };

  const handleSync = async ({ full = false, jobType = "all" } = {}) => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await startGmailSync({ full, after: syncAfter, before: syncBefore, jobType });
      setSyncJobId(res.job_id);
      // Polling will handle the rest
    } catch (err) {
      setSyncing(false);
      setSyncResult({ error: err.response?.data?.detail || "Sync failed" });
    }
  };

  const handleDisconnect = async () => {
    await disconnectGmail();
    setGmailStatus({ connected: false });
    setSyncResult(null);
    setStmtResult(null);
  };

  const handleClearData = async () => {
    await clearAllData();
    setShowClearConfirm(false);
    setResult(null);
    setSyncResult(null);
    setStmtResult(null);
    refreshAll();
  };

  const handleAddPassword = async () => {
    if (!newPwValue) return;
    await addPassword(newPwLabel || "Untitled", newPwValue);
    setNewPwLabel("");
    setNewPwValue("");
    getPasswords().then(setPasswords).catch(() => {});
  };

  const handleDeletePassword = async (id) => {
    await deletePassword(id);
    getPasswords().then(setPasswords).catch(() => {});
  };

  const summary = gmailStatus?.import_summary;

  return (
    <div>
      <div className="page-header">
        <h1>Import Transactions</h1>
        <p>Connect Gmail or upload PDF statements</p>
      </div>

      {/* ===== GMAIL SECTION ===== */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Mail size={18} /> Gmail
        </h2>

        {gmailStatus?.connected ? (
          <div>
            {/* Connected badge + summary */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
              <span style={{ background: "var(--green-bg)", border: "1px solid var(--green)", borderRadius: 6, padding: "4px 10px", fontSize: 12, color: "var(--green)", display: "flex", alignItems: "center", gap: 4 }}>
                <CheckCircle size={12} /> {gmailStatus.email}
              </span>
              {gmailStatus.last_sync && (
                <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                  Synced {new Date(gmailStatus.last_sync).toLocaleDateString()}
                </span>
              )}
              <button className="secondary" onClick={handleDisconnect} style={{ padding: "3px 8px", minHeight: 0, fontSize: 11 }}>
                Disconnect
              </button>
            </div>

            {/* Import summary bar */}
            {summary?.total_transactions > 0 && (
              <div style={{ background: "var(--bg-input)", borderRadius: 8, padding: "10px 14px", marginBottom: 16, display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
                <div>
                  <span style={{ fontSize: 18, fontWeight: 700 }}>{summary.total_transactions}</span>
                  <span style={{ fontSize: 11, color: "var(--text-dim)", marginLeft: 4 }}>imported</span>
                </div>
                <span style={{ color: "var(--border)" }}>|</span>
                <span style={{ fontSize: 12 }}>
                  {summary.earliest_date?.substring(0, 10)} → {summary.latest_date?.substring(0, 10)}
                </span>
                <span style={{ color: "var(--border)" }}>|</span>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {Object.entries(summary.by_source || {}).map(([src, cnt]) => {
                    const bank = src.includes("hdfc") ? "HDFC" : src.includes("axis") ? "Axis" : src.includes("scapia") ? "Scapia" : src.includes("upi") ? "UPI" : src === "manual" ? "Manual" : src;
                    return <span key={src} style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: "rgba(99,102,241,0.12)", color: "var(--accent)" }}>{bank}: {cnt}</span>;
                  })}
                </div>
              </div>
            )}

            {/* Sync controls */}
            {syncing ? (
              <div style={{ background: "var(--bg-input)", borderRadius: 10, padding: 20, textAlign: "center" }}>
                <RefreshCw size={24} style={{ color: "var(--accent)", animation: "spin 1s linear infinite" }} />
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 10 }}>Syncing your transactions...</div>
                <p style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>
                  This may take 1-2 minutes. You can navigate away — we'll keep syncing in the background.
                </p>
                <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
              </div>
            ) : (
              <div>
                {/* Date range (optional) */}
                <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
                  <Calendar size={14} style={{ color: "var(--text-dim)" }} />
                  <input type="date" value={syncAfter} onChange={(e) => setSyncAfter(e.target.value)} style={{ flex: "1 1 120px", minWidth: 0, minHeight: 36, fontSize: 13 }} />
                  <span style={{ color: "var(--text-dim)", fontSize: 12 }}>to</span>
                  <input type="date" value={syncBefore} onChange={(e) => setSyncBefore(e.target.value)} style={{ flex: "1 1 120px", minWidth: 0, minHeight: 36, fontSize: 13 }} />
                  {(syncAfter || syncBefore) && (
                    <button className="secondary" onClick={() => { setSyncAfter(""); setSyncBefore(""); }} style={{ padding: "6px 10px", minHeight: 36 }}><X size={12} /></button>
                  )}
                </div>

                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button onClick={() => handleSync()} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, fontSize: 14, padding: "12px 16px" }}>
                    <RefreshCw size={16} />
                    {syncAfter ? "Sync Date Range" : "Sync All"}
                  </button>
                  {!syncAfter && !syncBefore && (
                    <button className="secondary" onClick={() => handleSync({ full: true })} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, padding: "10px 14px" }}>
                      Full Resync
                    </button>
                  )}
                </div>

                <p style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 8 }}>
                  Syncs transaction alerts + downloads CC/bank statement PDFs from Gmail in one go.
                </p>
              </div>
            )}

            {/* Results */}
            {syncResult && !syncResult.error && (
              <>
                {syncResult.alerts && <SyncResultCard title="Transaction Alerts" result={syncResult.alerts} type="alerts" />}
                {syncResult.statements && <SyncResultCard title="PDF Statements" result={syncResult.statements} type="statements" />}
              </>
            )}
            {syncResult?.error && <ErrorMsg msg={syncResult.error} />}

            {/* Supported banks info */}
            <div style={{ background: "var(--bg-input)", borderRadius: 8, padding: "10px 14px", marginTop: 14, fontSize: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 6, color: "var(--text-dim)" }}>Supported Banks</div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 8 }}>
                {[
                  { name: "HDFC", alerts: true, statements: true },
                  { name: "Axis", alerts: false, statements: true },
                  { name: "Scapia", alerts: true, statements: false },
                  { name: "ICICI", alerts: false, statements: true },
                  { name: "Kotak", alerts: false, statements: true },
                  { name: "SBI", alerts: false, statements: true },
                ].map((b) => (
                  <span key={b.name} style={{ padding: "3px 8px", borderRadius: 4, background: "rgba(99,102,241,0.1)", color: "var(--accent)", fontSize: 11 }}>
                    {b.name}
                    {b.alerts && " ✉"}
                    {b.statements && " 📄"}
                  </span>
                ))}
              </div>
              <div style={{ color: "var(--text-dim)", lineHeight: 1.5, fontSize: 11 }}>
                ✉ = Email alerts parsed &nbsp; 📄 = PDF statements parsed<br />
                CC payments/refunds tracked separately from income.
              </div>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "16px 0" }}>
            <p style={{ color: "var(--text-dim)", marginBottom: 14, fontSize: 13, lineHeight: 1.5 }}>
              Connect your Gmail to automatically import transaction alerts and download statement PDFs from HDFC, Axis, Scapia, and more. We only read bank-related emails.
            </p>
            <button onClick={handleConnectGmail} style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 24px" }}>
              <Mail size={18} /> Connect Gmail
            </button>
          </div>
        )}
      </div>

      {/* ===== PDF PASSWORDS ===== */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Key size={18} /> PDF Passwords
        </h2>
        <p style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 10 }}>
          Indian bank PDFs are password-protected. Saved passwords are tried automatically during Gmail statement sync and manual uploads.
        </p>
        {passwords.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            {passwords.map((pw) => (
              <div key={pw.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 10px", background: "var(--bg-input)", borderRadius: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 13 }}>{pw.label}</span>
                <button onClick={() => handleDeletePassword(pw.id)} style={{ background: "none", border: "none", color: "var(--text-dim)", padding: 4, minHeight: 0, cursor: "pointer" }}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input type="text" value={newPwLabel} onChange={(e) => setNewPwLabel(e.target.value)} placeholder="Label (e.g. HDFC CC)" style={{ flex: "1 1 100px", minWidth: 0 }} />
          <input type="password" value={newPwValue} onChange={(e) => setNewPwValue(e.target.value)} placeholder="Password" style={{ flex: "1 1 100px", minWidth: 0 }} />
          <button onClick={handleAddPassword} disabled={!newPwValue} style={{ whiteSpace: "nowrap" }}>+ Add</button>
        </div>
      </div>

      {/* ===== MANUAL PDF UPLOAD ===== */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FileText size={18} /> Manual PDF Upload
        </h2>
        <div
          className={`upload-zone ${dragover ? "dragover" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
          onDragLeave={() => setDragover(false)}
          onDrop={handleDrop}
        >
          <input ref={inputRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={(e) => setFile(e.target.files[0])} />
          {file ? (
            <>
              <FileText size={36} color="var(--accent)" />
              <p style={{ color: "var(--text)", fontWeight: 600, marginTop: 6 }}>{file.name}</p>
              <p style={{ fontSize: 12 }}>{(file.size / 1024).toFixed(1)} KB</p>
            </>
          ) : (
            <>
              <Upload size={36} color="var(--text-dim)" />
              <p>Drop a PDF here or tap to browse</p>
              <p style={{ fontSize: 11 }}>Bank statements, credit card bills, UPI exports</p>
            </>
          )}
        </div>
        <div className="upload-actions" style={{ display: "flex", gap: 10, marginTop: 14, alignItems: "center" }}>
          <div className="form-group" style={{ margin: 0, flex: 1 }}>
            <label>Type</label>
            <select value={fileType} onChange={(e) => setFileType(e.target.value)}>
              <option value="auto">Auto-detect</option>
              <option value="bank_statement">Bank Statement</option>
              <option value="credit_card">Credit Card</option>
              <option value="upi">UPI</option>
            </select>
          </div>
          <div className="form-group" style={{ margin: 0, flex: 1 }}>
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="If protected" />
          </div>
          <button onClick={handleUpload} disabled={!file || uploading} style={{ marginTop: 18 }}>
            {uploading ? "Parsing..." : "Upload"}
          </button>
        </div>
        {error && <ErrorMsg msg={error} />}
      </div>

      {/* Upload result */}
      {result && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
            <StatCard value={result.transactions_found} label="Imported" color="green" />
            {result.duplicates_skipped > 0 && <StatCard value={result.duplicates_skipped} label="Duplicates" color="yellow" />}
            <div style={{ flex: 1, minWidth: 100, background: "var(--bg-input)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 14px", textAlign: "center" }}>
              <div style={{ fontSize: 13, color: "var(--text-dim)" }}>Type</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{result.file_type.replace("_", " ")}</div>
            </div>
          </div>

          {result.duplicates_skipped > 0 && result.duplicate_transactions?.length > 0 && (
            <div>
              <button className="secondary" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }} onClick={() => setShowDuplicates(!showDuplicates)}>
                {showDuplicates ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {showDuplicates ? "Hide" : "Show"} {result.duplicates_skipped} duplicates
              </button>
              {showDuplicates && (
                <div style={{ marginTop: 8, maxHeight: 200, overflowY: "auto" }}>
                  {result.duplicate_transactions.map((t, i) => (
                    <div key={i} style={{ fontSize: 12, padding: "4px 0", color: "var(--text-dim)", borderBottom: "1px solid var(--border)" }}>
                      {t.date?.substring(0, 10)} · {t.description?.substring(0, 30)} · ₹{t.amount}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Upload history */}
      {history.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h2>Upload History</h2>
          <table className="responsive-table">
            <thead><tr><th>File</th><th>Type</th><th>Txns</th><th>Date</th></tr></thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id}>
                  <td data-label="File" style={{ wordBreak: "break-all" }}>{h.filename}</td>
                  <td data-label="Type"><span className="tag default">{h.file_type}</span></td>
                  <td data-label="Txns">{h.transactions_found}</td>
                  <td data-label="Date">{new Date(h.uploaded_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Danger zone */}
      <div className="card" style={{ borderColor: "var(--red)" }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--red)" }}>
          <AlertOctagon size={18} /> Danger Zone
        </h2>
        {!showClearConfirm ? (
          <button className="danger" onClick={() => setShowClearConfirm(true)} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Trash2 size={14} /> Clear All Transaction Data
          </button>
        ) : (
          <div style={{ background: "var(--red-bg)", border: "1px solid var(--red)", borderRadius: 8, padding: 14 }}>
            <p style={{ marginBottom: 10, fontSize: 13, fontWeight: 600 }}>
              Permanently delete all expenses and upload history. Passwords and Gmail connection are kept.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="danger" onClick={handleClearData}>Yes, Delete</button>
              <button className="secondary" onClick={() => setShowClearConfirm(false)}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Helper components

function SyncResultCard({ title, result, type }) {
  return (
    <div style={{ marginTop: 12, background: "var(--bg-input)", borderRadius: 8, padding: 14 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>{title}</div>
      <div style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
        <StatCard value={result.imported} label="New" color="green" small />
        <StatCard value={result.duplicates} label="Duplicates" color="yellow" small />
        {result.emails_scanned != null && <StatCard value={result.emails_scanned} label="Scanned" color="dim" small />}
      </div>

      {/* Bank breakdown for alerts */}
      {result.alerts_by_bank?.length > 0 && (
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 4 }}>
          {result.alerts_by_bank.map((b, i) => (
            <span key={i} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: "rgba(99,102,241,0.12)", color: "var(--accent)", fontWeight: 600 }}>
              {b.bank.toUpperCase()}: {b.count}
            </span>
          ))}
        </div>
      )}

      {/* Statement list */}
      {result.statements?.length > 0 && (
        <div style={{ marginTop: 6 }}>
          {result.statements.map((s, i) => (
            <div key={i} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "6px 8px", borderRadius: 6, marginBottom: 3,
              background: s.status === "failed" ? "var(--red-bg)" : "var(--bg-card)",
              border: s.status === "failed" ? "1px solid var(--red)" : "1px solid var(--border)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
                <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 3, background: "rgba(99,102,241,0.12)", color: "var(--accent)", flexShrink: 0, textTransform: "uppercase" }}>
                  {s.bank}
                </span>
                {s.type && (
                  <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 3, background: s.type === "Credit Card" ? "rgba(236,72,153,0.15)" : "rgba(34,197,94,0.15)", color: s.type === "Credit Card" ? "#ec4899" : "var(--green)", flexShrink: 0 }}>
                    {s.type === "Credit Card" ? "CC" : "Bank"}
                  </span>
                )}
                <span style={{ fontSize: 11, color: "var(--text-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {s.filename}
                </span>
              </div>
              <span style={{ fontSize: 11, fontWeight: 600, flexShrink: 0, marginLeft: 6, color: s.status === "failed" ? "var(--red)" : "var(--text)" }} title={s.reason || ""}>
                {s.status === "failed" ? (
                  <span style={{ display: "flex", alignItems: "center", gap: 4, flexDirection: "column", textAlign: "right" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
                      <AlertCircle size={12} />
                      {s.reason?.includes("password") || s.reason?.includes("check password") ? "Wrong password" : s.reason?.includes("0 transactions") ? "Unsupported format" : "Parse failed"}
                    </span>
                    <span style={{ fontSize: 9, fontWeight: 400, color: "var(--text-dim)", maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.reason}
                    </span>
                  </span>
                ) : (
                  `${s.transactions} txns`
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      {result.date_range?.after && (
        <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 6 }}>
          Searched: {result.date_range.after} → {result.date_range.before || "now"}
        </div>
      )}
    </div>
  );
}

function StatCard({ value, label, color, small }) {
  const colors = {
    green: { bg: "var(--green-bg)", border: "var(--green)", text: "var(--green)" },
    yellow: { bg: "var(--yellow-bg)", border: "var(--yellow)", text: "var(--yellow)" },
    dim: { bg: "var(--bg-card)", border: "var(--border)", text: "var(--text-dim)" },
  };
  const c = colors[color] || colors.dim;
  return (
    <div style={{
      flex: 1, minWidth: small ? 60 : 80,
      background: c.bg, border: `1px solid ${c.border}`,
      borderRadius: 8, padding: small ? "6px 10px" : "8px 14px", textAlign: "center",
    }}>
      <div style={{ fontSize: small ? 16 : 18, fontWeight: 700, color: c.text }}>{value}</div>
      <div style={{ fontSize: small ? 9 : 10, color: c.text }}>{label}</div>
    </div>
  );
}

function ErrorMsg({ msg }) {
  return (
    <p style={{ color: "var(--red)", marginTop: 10, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
      <AlertTriangle size={14} /> {msg}
    </p>
  );
}
