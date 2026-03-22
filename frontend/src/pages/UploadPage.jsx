import { useState, useRef } from "react";
import { Upload, FileText, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, Mail, RefreshCw, Unlink } from "lucide-react";
import { uploadStatement, getUploadHistory, getGmailStatus, getGmailAuthUrl, startGmailSync, disconnectGmail } from "../api/client";
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

  useEffect(() => {
    getUploadHistory().then(setHistory).catch(() => {});
    getGmailStatus().then(setGmailStatus).catch(() => {});
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

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await startGmailSync();
      setSyncResult(res);
      getGmailStatus().then(setGmailStatus).catch(() => {});
      getUploadHistory().then(setHistory).catch(() => {});
    } catch (err) {
      setSyncResult({ error: err.response?.data?.detail || "Sync failed" });
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    await disconnectGmail();
    setGmailStatus({ connected: false });
    setSyncResult(null);
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
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
              <div style={{
                background: "var(--green-bg)", border: "1px solid var(--green)",
                borderRadius: 8, padding: "6px 12px", fontSize: 13, color: "var(--green)",
                display: "flex", alignItems: "center", gap: 6,
              }}>
                <CheckCircle size={14} /> {gmailStatus.email}
              </div>
              {gmailStatus.last_sync && (
                <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
                  Last sync: {new Date(gmailStatus.last_sync).toLocaleString()}
                </span>
              )}
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button onClick={handleSync} disabled={syncing} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <RefreshCw size={16} className={syncing ? "spin" : ""} />
                {syncing ? "Syncing..." : "Sync Now"}
              </button>
              <button className="secondary" onClick={handleDisconnect} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Unlink size={14} /> Disconnect
              </button>
            </div>

            {syncResult && !syncResult.error && (
              <div style={{ display: "flex", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
                <div style={{
                  flex: 1, minWidth: 100, background: "var(--green-bg)", border: "1px solid var(--green)",
                  borderRadius: 10, padding: "10px 14px", textAlign: "center"
                }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: "var(--green)" }}>{syncResult.imported}</div>
                  <div style={{ fontSize: 11, color: "var(--green)" }}>Imported</div>
                </div>
                {syncResult.duplicates > 0 && (
                  <div style={{
                    flex: 1, minWidth: 100, background: "var(--yellow-bg)", border: "1px solid var(--yellow)",
                    borderRadius: 10, padding: "10px 14px", textAlign: "center"
                  }}>
                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--yellow)" }}>{syncResult.duplicates}</div>
                    <div style={{ fontSize: 11, color: "var(--yellow)" }}>Duplicates</div>
                  </div>
                )}
                <div style={{
                  flex: 1, minWidth: 100, background: "var(--bg-input)", border: "1px solid var(--border)",
                  borderRadius: 10, padding: "10px 14px", textAlign: "center"
                }}>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>{syncResult.emails_scanned}</div>
                  <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Emails Scanned</div>
                </div>
              </div>
            )}
            {syncResult?.error && (
              <p style={{ color: "var(--red)", marginTop: 12 }}>{syncResult.error}</p>
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
    </div>
  );
}
