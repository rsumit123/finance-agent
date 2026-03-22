import { useState, useRef } from "react";
import { Upload, FileText, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, Mail, RefreshCw, Unlink, Key, Trash2, FileSearch, AlertOctagon } from "lucide-react";
import { uploadStatement, getUploadHistory, getGmailStatus, getGmailAuthUrl, startGmailSync, disconnectGmail, syncStatements, getPasswords, addPassword, deletePassword, clearAllData } from "../api/client";
import { useEffect } from "react";

function formatINR(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function UploadPage() {
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
  const [syncResult, setSyncResult] = useState(null);
  const [syncingStatements, setSyncingStatements] = useState(false);
  const [stmtResult, setStmtResult] = useState(null);

  // Password state
  const [passwords, setPasswords] = useState([]);
  const [newPwLabel, setNewPwLabel] = useState("");
  const [newPwValue, setNewPwValue] = useState("");

  useEffect(() => {
    getUploadHistory().then(setHistory).catch(() => {});
    getGmailStatus().then(setGmailStatus).catch(() => {});
    getPasswords().then(setPasswords).catch(() => {});
  }, [result]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const res = await uploadStatement(file, fileType, password);
      setResult(res);
      setFile(null);
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
    if (droppedFile?.name.toLowerCase().endsWith(".pdf")) {
      setFile(droppedFile);
    }
  };

  const handleConnectGmail = async () => {
    try {
      const { auth_url } = await getGmailAuthUrl();
      window.location.href = auth_url;
    } catch {
      setError("Failed to start Gmail connection. Check server config.");
    }
  };

  const [syncAfter, setSyncAfter] = useState("");
  const [syncBefore, setSyncBefore] = useState("");

  const handleSync = async ({ full = false } = {}) => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await startGmailSync({ full, after: syncAfter, before: syncBefore });
      setSyncResult(res);
      getGmailStatus().then(setGmailStatus).catch(() => {});
      getUploadHistory().then(setHistory).catch(() => {});
    } catch (err) {
      setSyncResult({ error: err.response?.data?.detail || "Sync failed" });
    } finally {
      setSyncing(false);
    }
  };

  const handleSyncStatements = async () => {
    setSyncingStatements(true);
    setStmtResult(null);
    try {
      const res = await syncStatements();
      setStmtResult(res);
      getUploadHistory().then(setHistory).catch(() => {});
    } catch (err) {
      setStmtResult({ error: err.response?.data?.detail || "Statement sync failed" });
    } finally {
      setSyncingStatements(false);
    }
  };

  const handleDisconnect = async () => {
    await disconnectGmail();
    setGmailStatus({ connected: false });
    setSyncResult(null);
    setStmtResult(null);
  };

  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const handleClearData = async () => {
    await clearAllData();
    setShowClearConfirm(false);
    setResult(null);
    setSyncResult(null);
    setStmtResult(null);
    getUploadHistory().then(setHistory).catch(() => {});
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

  return (
    <div>
      <div className="page-header">
        <h1>Import Transactions</h1>
        <p>Connect Gmail or upload PDF statements</p>
      </div>

      {/* Gmail Integration */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Mail size={18} /> Gmail Sync
        </h2>

        {gmailStatus?.connected ? (
          <div>
            {/* Connection + Import Summary */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
              <div style={{
                background: "var(--green-bg)", border: "1px solid var(--green)",
                borderRadius: 8, padding: "6px 12px", fontSize: 13, color: "var(--green)",
                display: "flex", alignItems: "center", gap: 6,
              }}>
                <CheckCircle size={14} /> {gmailStatus.email}
              </div>
              <button className="secondary" onClick={handleDisconnect} style={{ padding: "4px 10px", minHeight: 0, fontSize: 12 }}>
                <Unlink size={12} />
              </button>
            </div>

            {/* Import Status Dashboard */}
            {gmailStatus.import_summary?.total_transactions > 0 && (
              <div style={{
                background: "var(--bg-input)", borderRadius: 10, padding: "12px 16px", marginBottom: 16,
                display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center",
              }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700 }}>{gmailStatus.import_summary.total_transactions}</div>
                  <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Total Imported</div>
                </div>
                <div style={{ width: 1, height: 36, background: "var(--border)" }} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>
                    {gmailStatus.import_summary.earliest_date?.substring(0, 10)} → {gmailStatus.import_summary.latest_date?.substring(0, 10)}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Date Range</div>
                </div>
                <div style={{ width: 1, height: 36, background: "var(--border)" }} />
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {Object.entries(gmailStatus.import_summary.by_source || {}).map(([src, cnt]) => {
                    const bank = src.includes("hdfc") ? "HDFC" : src.includes("axis") ? "Axis" : src.includes("scapia") ? "Scapia" : src.includes("upi") ? "UPI" : src === "manual" ? "Manual" : src;
                    return (
                      <span key={src} style={{
                        fontSize: 11, padding: "2px 8px", borderRadius: 4,
                        background: "rgba(99,102,241,0.12)", color: "var(--accent)",
                      }}>
                        {bank}: {cnt}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Sync Controls */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 6 }}>Custom date range (optional)</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                <input type="date" value={syncAfter} onChange={(e) => setSyncAfter(e.target.value)} style={{ width: "auto", flex: "0 1 150px" }} placeholder="From" />
                <span style={{ color: "var(--text-dim)", fontSize: 12 }}>to</span>
                <input type="date" value={syncBefore} onChange={(e) => setSyncBefore(e.target.value)} style={{ width: "auto", flex: "0 1 150px" }} placeholder="To" />
                {(syncAfter || syncBefore) && (
                  <button className="secondary" onClick={() => { setSyncAfter(""); setSyncBefore(""); }} style={{ padding: "6px 10px", minHeight: 0, fontSize: 12 }}>
                    <X size={12} /> Clear
                  </button>
                )}
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => handleSync()} disabled={syncing} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <RefreshCw size={16} />
                {syncing ? "Syncing..." : syncAfter || syncBefore ? "Sync Date Range" : "Sync New Alerts"}
              </button>
              <button className="secondary" onClick={() => handleSync({ full: true })} disabled={syncing} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <RefreshCw size={16} />
                Full Resync (90 days)
              </button>
              <button onClick={handleSyncStatements} disabled={syncingStatements} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <FileSearch size={16} />
                {syncingStatements ? "Scanning..." : "Find Statements"}
              </button>
            </div>

            {gmailStatus.last_sync && (
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 8 }}>
                Last sync: {new Date(gmailStatus.last_sync).toLocaleString()}
                {" · "}Only debits are imported (credits/refunds are excluded)
              </div>
            )}

            {/* Alert sync results */}
            {syncResult && !syncResult.error && (
              <div style={{ marginTop: 16, background: "var(--bg-input)", borderRadius: 10, padding: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>Transaction Alerts</span>
                  <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{syncResult.emails_scanned} emails scanned</span>
                </div>

                <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
                  <div style={{ background: "var(--green-bg)", border: "1px solid var(--green)", borderRadius: 8, padding: "8px 16px", textAlign: "center", flex: 1, minWidth: 80 }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "var(--green)" }}>{syncResult.imported}</div>
                    <div style={{ fontSize: 10, color: "var(--green)" }}>New</div>
                  </div>
                  <div style={{ background: "var(--yellow-bg)", border: "1px solid var(--yellow)", borderRadius: 8, padding: "8px 16px", textAlign: "center", flex: 1, minWidth: 80 }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "var(--yellow)" }}>{syncResult.duplicates}</div>
                    <div style={{ fontSize: 10, color: "var(--yellow)" }}>Duplicates</div>
                  </div>
                </div>

                {syncResult.alerts_by_bank?.length > 0 && (
                  <div>
                    <span style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.05em" }}>By Bank</span>
                    <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                      {syncResult.alerts_by_bank.map((b, i) => (
                        <span key={i} style={{
                          padding: "4px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                          background: "rgba(99,102,241,0.15)", color: "var(--accent)",
                        }}>
                          {b.bank.toUpperCase()} — {b.count}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            {syncResult?.error && (
              <p style={{ color: "var(--red)", marginTop: 12 }}>{syncResult.error}</p>
            )}

            {/* Statement sync results */}
            {stmtResult && !stmtResult.error && (
              <div style={{ marginTop: 12, background: "var(--bg-input)", borderRadius: 10, padding: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>PDF Statements</span>
                  <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{stmtResult.statements_found} PDFs found</span>
                </div>

                <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
                  <div style={{ background: "var(--green-bg)", border: "1px solid var(--green)", borderRadius: 8, padding: "8px 16px", textAlign: "center", flex: 1, minWidth: 80 }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "var(--green)" }}>{stmtResult.imported}</div>
                    <div style={{ fontSize: 10, color: "var(--green)" }}>New</div>
                  </div>
                  <div style={{ background: "var(--yellow-bg)", border: "1px solid var(--yellow)", borderRadius: 8, padding: "8px 16px", textAlign: "center", flex: 1, minWidth: 80 }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "var(--yellow)" }}>{stmtResult.duplicates}</div>
                    <div style={{ fontSize: 10, color: "var(--yellow)" }}>Duplicates</div>
                  </div>
                </div>

                {stmtResult.statements?.length > 0 && (
                  <div>
                    <span style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Statements Found</span>
                    {stmtResult.statements.map((s, i) => (
                      <div key={i} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "8px 10px", borderRadius: 6, marginTop: 6,
                        background: "var(--bg-card)", border: "1px solid var(--border)",
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                          <span style={{
                            fontWeight: 700, textTransform: "uppercase", fontSize: 11,
                            padding: "3px 8px", borderRadius: 4, flexShrink: 0,
                            background: "rgba(99,102,241,0.15)", color: "var(--accent)",
                          }}>
                            {s.bank}
                          </span>
                          <span style={{ fontSize: 12, color: "var(--text-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {s.filename}
                          </span>
                        </div>
                        <span style={{ fontWeight: 600, fontSize: 13, flexShrink: 0, marginLeft: 8 }}>
                          {s.transactions} txns
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {stmtResult.statements_found === 0 && (
                  <p style={{ fontSize: 13, color: "var(--text-dim)", textAlign: "center" }}>
                    No statement PDFs found in your email. Banks may not attach PDFs — try manual upload instead.
                  </p>
                )}
              </div>
            )}
            {stmtResult?.error && (
              <p style={{ color: "var(--red)", marginTop: 12 }}>{stmtResult.error}</p>
            )}
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "20px 0" }}>
            <p style={{ color: "var(--text-dim)", marginBottom: 16, fontSize: 14 }}>
              Connect your Gmail to automatically import transaction alerts from HDFC Bank, Axis Bank, and more.
              We only read bank alert emails — nothing else.
            </p>
            <button onClick={handleConnectGmail} style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 24px", fontSize: 15 }}>
              <Mail size={18} /> Connect Gmail
            </button>
          </div>
        )}
      </div>

      {/* PDF Passwords */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Key size={18} /> PDF Passwords
        </h2>
        <p style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 12 }}>
          Indian bank statements are password-protected. Save your passwords here — they'll be used for both manual uploads and Gmail statement sync.
        </p>

        {passwords.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            {passwords.map((pw) => (
              <div key={pw.id} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "8px 12px", background: "var(--bg-input)", borderRadius: 8, marginBottom: 6,
              }}>
                <span style={{ fontSize: 14 }}>{pw.label}</span>
                <button
                  onClick={() => handleDeletePassword(pw.id)}
                  style={{ background: "none", border: "none", color: "var(--text-dim)", padding: 4, minHeight: 0, cursor: "pointer" }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            type="text"
            value={newPwLabel}
            onChange={(e) => setNewPwLabel(e.target.value)}
            placeholder="Label (e.g. HDFC CC)"
            style={{ flex: 1, minWidth: 100 }}
          />
          <input
            type="password"
            value={newPwValue}
            onChange={(e) => setNewPwValue(e.target.value)}
            placeholder="Password"
            style={{ flex: 1, minWidth: 100 }}
          />
          <button onClick={handleAddPassword} disabled={!newPwValue} style={{ whiteSpace: "nowrap" }}>
            + Add
          </button>
        </div>
      </div>

      {/* PDF Upload */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FileText size={18} /> PDF Upload
        </h2>
        <div
          className={`upload-zone ${dragover ? "dragover" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
          onDragLeave={() => setDragover(false)}
          onDrop={handleDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            style={{ display: "none" }}
            onChange={(e) => setFile(e.target.files[0])}
          />
          {file ? (
            <>
              <FileText size={40} color="var(--accent)" />
              <p style={{ color: "var(--text)", fontWeight: 600, marginTop: 8 }}>
                {file.name}
              </p>
              <p>{(file.size / 1024).toFixed(1)} KB</p>
            </>
          ) : (
            <>
              <Upload size={40} color="var(--text-dim)" />
              <p>Drop a PDF here or click to browse</p>
              <p style={{ fontSize: 12 }}>
                Supports: Bank statements, Credit card bills, UPI exports
              </p>
            </>
          )}
        </div>

        <div className="upload-actions" style={{ display: "flex", gap: 12, marginTop: 16, alignItems: "center" }}>
          <div className="form-group" style={{ margin: 0, flex: 1 }}>
            <label>Statement Type</label>
            <select value={fileType} onChange={(e) => setFileType(e.target.value)}>
              <option value="auto">Auto-detect</option>
              <option value="bank_statement">Bank Statement</option>
              <option value="credit_card">Credit Card Bill</option>
              <option value="upi">UPI Transactions</option>
            </select>
          </div>
          <div className="form-group" style={{ margin: 0, flex: 1 }}>
            <label>PDF Password (if protected)</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Leave blank if none"
            />
          </div>
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            style={{ marginTop: 18 }}
          >
            {uploading ? "Parsing..." : "Upload & Parse"}
          </button>
        </div>

        {error && (
          <p style={{ color: "var(--red)", marginTop: 12 }}>{error}</p>
        )}
      </div>

      {/* Result */}
      {result && (
        <div className="card" style={{ marginBottom: 24 }}>
          {/* Summary bar */}
          <div style={{
            display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap"
          }}>
            <div style={{
              flex: 1, minWidth: 120, background: "var(--green-bg)", border: "1px solid var(--green)",
              borderRadius: 10, padding: "12px 16px", textAlign: "center"
            }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--green)" }}>{result.transactions_found}</div>
              <div style={{ fontSize: 12, color: "var(--green)", marginTop: 2 }}>Imported</div>
            </div>
            {result.duplicates_skipped > 0 && (
              <div style={{
                flex: 1, minWidth: 120, background: "var(--yellow-bg)", border: "1px solid var(--yellow)",
                borderRadius: 10, padding: "12px 16px", textAlign: "center"
              }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: "var(--yellow)" }}>{result.duplicates_skipped}</div>
                <div style={{ fontSize: 12, color: "var(--yellow)", marginTop: 2 }}>Duplicates Skipped</div>
              </div>
            )}
            <div style={{
              flex: 1, minWidth: 120, background: "var(--bg-input)", border: "1px solid var(--border)",
              borderRadius: 10, padding: "12px 16px", textAlign: "center"
            }}>
              <div style={{ fontSize: 13, color: "var(--text-dim)" }}>Detected as</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{result.file_type.replace("_", " ")}</div>
            </div>
          </div>

          {result.transactions.length > 0 && (
            <table className="responsive-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Category</th>
                  <th>Payment</th>
                  <th style={{ textAlign: "right" }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {result.transactions.slice(0, 20).map((t) => (
                  <tr key={t.id}>
                    <td data-label="Date">{t.date}</td>
                    <td data-label="Description">{t.description || "—"}</td>
                    <td data-label="Category"><span className="tag default">{t.category}</span></td>
                    <td data-label="Payment"><span className="tag default">{t.payment_method.replace("_", " ")}</span></td>
                    <td data-label="Amount" style={{ fontWeight: 600 }}>{formatINR(t.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.transactions.length > 20 && (
            <p style={{ color: "var(--text-dim)", marginTop: 12 }}>
              Showing 20 of {result.transactions.length}. View all in Expenses.
            </p>
          )}

          {result.duplicates_skipped > 0 && result.duplicate_transactions?.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <button
                className="secondary"
                style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
                onClick={() => setShowDuplicates(!showDuplicates)}
              >
                {showDuplicates ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {showDuplicates ? "Hide" : "Show"} {result.duplicates_skipped} skipped duplicates
              </button>
              {showDuplicates && (
                <table className="responsive-table" style={{ marginTop: 12 }}>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Description</th>
                      <th>Category</th>
                      <th style={{ textAlign: "right" }}>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.duplicate_transactions.map((t, i) => (
                      <tr key={i} style={{ opacity: 0.6 }}>
                        <td data-label="Date">{t.date}</td>
                        <td data-label="Description">{t.description || "—"}</td>
                        <td data-label="Category"><span className="tag default">{t.category}</span></td>
                        <td data-label="Amount" style={{ fontWeight: 600 }}>{formatINR(t.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {/* Upload History */}
      {history.length > 0 && (
        <div className="card">
          <h2>Upload History</h2>
          <table className="responsive-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Type</th>
                <th>Transactions</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id}>
                  <td data-label="File" style={{ wordBreak: "break-all" }}>{h.filename}</td>
                  <td data-label="Type"><span className="tag default">{h.file_type}</span></td>
                  <td data-label="Transactions">{h.transactions_found}</td>
                  <td data-label="Uploaded">{new Date(h.uploaded_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Danger Zone */}
      <div className="card" style={{ marginTop: 24, borderColor: "var(--red)" }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--red)" }}>
          <AlertOctagon size={18} /> Danger Zone
        </h2>
        {!showClearConfirm ? (
          <button
            className="danger"
            onClick={() => setShowClearConfirm(true)}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <Trash2 size={14} /> Clear All Transaction Data
          </button>
        ) : (
          <div style={{
            background: "var(--red-bg)", border: "1px solid var(--red)",
            borderRadius: 10, padding: 16,
          }}>
            <p style={{ marginBottom: 12, fontWeight: 600 }}>
              This will permanently delete all expenses and upload history. PDF passwords and Gmail connection will be kept.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="danger" onClick={handleClearData}>
                Yes, Delete Everything
              </button>
              <button className="secondary" onClick={() => setShowClearConfirm(false)}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
