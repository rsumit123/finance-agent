import { useState, useRef, useEffect } from "react";
import { Upload, FileText, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, Mail, RefreshCw, Unlink, Lock, Trash2, AlertOctagon, X, AlertCircle, Calendar, Loader, Info } from "lucide-react";
import { uploadStatement, getUploadHistory, getGmailStatus, getGmailAuthUrl, startGmailSync, getSyncStatus, getLatestSync, disconnectGmail, getPasswords, addPassword, deletePassword, clearAllData } from "../api/client";
import { isSmsAvailable, syncSmsMessages } from "../services/smsSync";
import { apiInstance } from "../api/client";
import { Smartphone } from "lucide-react";

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
  const [gmailLoading, setGmailLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncJobId, setSyncJobId] = useState(null);
  const [syncResult, setSyncResult] = useState(null);
  const [syncResultExpanded, setSyncResultExpanded] = useState(false);
  const [syncCompletedAt, setSyncCompletedAt] = useState(null);
  const [syncAfter, setSyncAfter] = useState("");
  const [syncBefore, setSyncBefore] = useState("");

  // Password state
  const [passwords, setPasswords] = useState([]);
  const [newPwLabel, setNewPwLabel] = useState("");
  const [newPwValue, setNewPwValue] = useState("");
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // SMS state
  const [smsAvailable] = useState(isSmsAvailable());
  const [smsSyncing, setSmsSyncing] = useState(false);
  const [smsResult, setSmsResult] = useState(null);

  const refreshAll = () => {
    setGmailLoading(true);
    Promise.all([
      getUploadHistory().then(setHistory).catch(() => {}),
      getGmailStatus().then(setGmailStatus).catch(() => {}),
      getPasswords().then(setPasswords).catch(() => {}),
      getLatestSync().then((job) => {
        if (job?.status === "completed" && job.result) {
          setSyncResult(job.result);
          setSyncCompletedAt(job.completed_at);
        }
        if (job?.status === "running" || job?.status === "pending") {
          setSyncing(true);
          setSyncJobId(job.job_id);
        }
      }).catch(() => {}),
    ]).finally(() => setGmailLoading(false));
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
          setSyncCompletedAt(job.completed_at);
          setSyncResultExpanded(true); // Auto-expand new results
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

  const handleSmsSync = async () => {
    setSmsSyncing(true);
    setSmsResult(null);
    try {
      const result = await syncSmsMessages(apiInstance, 90);
      setSmsResult(result);
      if (result && !result.error) refreshAll();
    } catch (err) {
      setSmsResult({ error: err.message || "SMS sync failed" });
    } finally {
      setSmsSyncing(false);
    }
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

      {/* ===== SMS SECTION (mobile only) ===== */}
      {smsAvailable && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Smartphone size={18} /> SMS Sync
            <InfoTip text="Reads transaction alert SMS from your phone's inbox. Extracts amount, merchant, date, and available balance from bank messages. Most accurate and real-time source." />
          </h2>

          <button onClick={handleSmsSync} disabled={smsSyncing}
            style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontSize: 14, padding: "14px 16px" }}>
            {smsSyncing ? (
              <><RefreshCw size={16} style={{ animation: "spin 1s linear infinite" }} /> Reading SMS...</>
            ) : (
              <><Smartphone size={16} /> Sync Bank SMS</>
            )}
          </button>

          {smsResult && !smsResult.error && (
            <div style={{ marginTop: 12, background: "var(--bg-input)", borderRadius: 8, padding: 12 }}>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <StatCard value={smsResult.imported} label="New" color="green" small />
                <StatCard value={smsResult.duplicates} label="Duplicates" color="yellow" small />
                <StatCard value={smsResult.messages_processed} label="SMS Read" color="dim" small />
                {smsResult.balances_extracted > 0 && (
                  <StatCard value={smsResult.balances_extracted} label="Balances" color="green" small />
                )}
              </div>
            </div>
          )}
          {smsResult?.error && <ErrorMsg msg={smsResult.error} />}
        </div>
      )}

      {/* ===== GMAIL SECTION ===== */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Mail size={18} /> Gmail Sync
          <InfoTip text="Automatically reads transaction alert emails and downloads credit card/bank statement PDFs from your Gmail. Only reads bank-related emails — nothing else." />
        </h2>

        {gmailLoading ? (
          <div style={{ textAlign: "center", padding: 24, color: "var(--text-dim)" }}>Loading...</div>
        ) : gmailStatus?.connected ? (
          <div>
            {/* Status line: email + stats + disconnect */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
              <span style={{ background: "var(--green-bg)", border: "1px solid var(--green)", borderRadius: 6, padding: "4px 10px", fontSize: 12, color: "var(--green)", display: "flex", alignItems: "center", gap: 4 }}>
                <CheckCircle size={12} /> {gmailStatus.email}
              </span>
              {summary?.total_transactions > 0 && (
                <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                  {summary.total_transactions} transactions · {summary.earliest_date?.substring(0, 10)} → {summary.latest_date?.substring(0, 10)}
                </span>
              )}
              <button className="secondary" onClick={handleDisconnect} style={{ padding: "3px 8px", minHeight: 0, fontSize: 11, marginLeft: "auto" }}>
                Disconnect
              </button>
            </div>

            <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>

            {/* Sync controls OR spinner */}
            {syncing ? (
              <div style={{ background: "var(--bg-input)", borderRadius: 10, padding: 20, textAlign: "center" }}>
                <RefreshCw size={24} style={{ color: "var(--accent)", animation: "spin 1s linear infinite" }} />
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 10 }}>Syncing your transactions...</div>
                <p style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>
                  This may take 1-2 minutes. You can navigate away — we'll keep syncing in the background.
                </p>
              </div>
            ) : (
              <button onClick={() => handleSync()} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontSize: 14, padding: "14px 16px" }}>
                <RefreshCw size={16} /> Sync All
              </button>
            )}

            {/* Advanced options — collapsible */}
            {!syncing && (
              <details style={{ marginTop: 8 }}>
                <summary style={{ fontSize: 11, color: "var(--text-dim)", cursor: "pointer", padding: "4px 0" }}>
                  Advanced: custom date range or full resync
                </summary>
                <div style={{ padding: "8px 0" }}>
                  <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap", alignItems: "center" }}>
                    <input type="date" value={syncAfter} onChange={(e) => setSyncAfter(e.target.value)} style={{ flex: "1 1 120px", minWidth: 0, minHeight: 34, fontSize: 12 }} />
                    <span style={{ color: "var(--text-dim)", fontSize: 11 }}>to</span>
                    <input type="date" value={syncBefore} onChange={(e) => setSyncBefore(e.target.value)} style={{ flex: "1 1 120px", minWidth: 0, minHeight: 34, fontSize: 12 }} />
                    {(syncAfter || syncBefore) && (
                      <button className="secondary" onClick={() => { setSyncAfter(""); setSyncBefore(""); }} style={{ padding: "4px 8px", minHeight: 34 }}><X size={12} /></button>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    {(syncAfter || syncBefore) && (
                      <button onClick={() => handleSync()} style={{ flex: 1, fontSize: 12, padding: "8px 12px" }}>
                        Sync Date Range
                      </button>
                    )}
                    <button className="secondary" onClick={() => handleSync({ full: true })} style={{ flex: 1, fontSize: 12, padding: "8px 12px" }}>
                      Full Resync (90 days)
                    </button>
                  </div>
                </div>
              </details>
            )}

            {/* Last sync results — collapsible */}
            {syncResult && !syncResult.error && (
              <div style={{ marginTop: 10 }}>
                <button
                  className="secondary"
                  onClick={() => setSyncResultExpanded(!syncResultExpanded)}
                  style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", fontSize: 12 }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <CheckCircle size={12} style={{ color: "var(--green)" }} />
                    Last sync{syncCompletedAt ? ": " + new Date(syncCompletedAt).toLocaleString() : ""}
                    {syncResult.alerts && ` · ${syncResult.alerts.imported || 0} new`}
                    {syncResult.alerts?.duplicates > 0 && ` · ${syncResult.alerts.duplicates} dupes`}
                    {syncResult.statements && ` · ${syncResult.statements.imported || 0} from PDFs`}
                  </span>
                  {syncResultExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
                {syncResultExpanded && (
                  <div style={{ background: "var(--bg-input)", borderRadius: "0 0 8px 8px", padding: "8px 0" }}>
                    {syncResult.alerts && <SyncResultCard title="Transaction Alerts" result={syncResult.alerts} type="alerts" />}
                    {syncResult.statements && <SyncResultCard title="PDF Statements" result={syncResult.statements} type="statements" />}
                  </div>
                )}
              </div>
            )}
            {syncResult?.error && <ErrorMsg msg={syncResult.error} />}

            {/* Supported banks — collapsible */}
            <details style={{ marginTop: 8 }}>
              <summary style={{ fontSize: 11, color: "var(--text-dim)", cursor: "pointer", padding: "4px 0" }}>
                Supported banks: HDFC, Axis, Scapia, ICICI, Kotak, SBI
              </summary>
              <div style={{ padding: "8px 0", display: "flex", gap: 4, flexWrap: "wrap" }}>
                {[
                  { name: "HDFC", alerts: true, statements: true },
                  { name: "Axis", alerts: false, statements: true },
                  { name: "Scapia", alerts: true, statements: false },
                  { name: "ICICI", alerts: false, statements: true },
                  { name: "Kotak", alerts: false, statements: true },
                  { name: "SBI", alerts: false, statements: true },
                ].map((b) => (
                  <span key={b.name} style={{ padding: "3px 8px", borderRadius: 4, background: "rgba(99,102,241,0.1)", color: "var(--accent)", fontSize: 11 }}>
                    {b.name} {b.alerts && "✉"} {b.statements && "📄"}
                  </span>
                ))}
              </div>
            </details>
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

      {/* ===== STATEMENT PASSWORDS ===== */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Lock size={18} /> Statement Passwords
          <InfoTip text="Indian bank and credit card statements are password-protected (usually your date of birth or PAN). Add your passwords here — they'll be tried automatically when syncing from Gmail or uploading manually." />
        </h2>
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

      {/* ===== MANUAL STATEMENT UPLOAD ===== */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Upload size={18} /> Manual Statement Upload
          <InfoTip text="Upload a bank statement, credit card bill, or UPI export PDF directly. We auto-detect the format (HDFC, Axis, PhonePe, etc.) and extract all transactions. Duplicates are skipped automatically." />
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

function InfoTip({ text }) {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position: "relative", display: "inline-flex" }}>
      <Info
        size={14}
        style={{ color: "var(--text-dim)", cursor: "pointer", opacity: 0.6 }}
        onClick={(e) => { e.stopPropagation(); setShow(!show); }}
      />
      {show && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 99 }} onClick={() => setShow(false)} />
          <div style={{
            position: "absolute", top: "100%", left: "50%", transform: "translateX(-50%)",
            marginTop: 6, width: 260, padding: "10px 14px",
            background: "var(--bg-card)", border: "1px solid var(--border)",
            borderRadius: 8, fontSize: 12, lineHeight: 1.5, color: "var(--text-dim)",
            zIndex: 100, boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
          }}>
            {text}
          </div>
        </>
      )}
    </span>
  );
}
