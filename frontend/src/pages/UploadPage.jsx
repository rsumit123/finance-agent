import { useState, useRef } from "react";
import { Upload, FileText, CheckCircle } from "lucide-react";
import { uploadStatement, getUploadHistory } from "../api/client";
import { useEffect } from "react";

function formatINR(n) {
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [fileType, setFileType] = useState("auto");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);
  const [dragover, setDragover] = useState(false);
  const inputRef = useRef();

  useEffect(() => {
    getUploadHistory().then(setHistory).catch(() => {});
  }, [result]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const res = await uploadStatement(file, fileType);
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

  return (
    <div>
      <div className="page-header">
        <h1>Upload Statement</h1>
        <p>Upload bank statements, credit card bills, or UPI transaction exports</p>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
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

        <div style={{ display: "flex", gap: 12, marginTop: 16, alignItems: "center" }}>
          <div className="form-group" style={{ margin: 0, flex: 1 }}>
            <label>Statement Type</label>
            <select value={fileType} onChange={(e) => setFileType(e.target.value)}>
              <option value="auto">Auto-detect</option>
              <option value="bank_statement">Bank Statement</option>
              <option value="credit_card">Credit Card Bill</option>
              <option value="upi">UPI Transactions</option>
            </select>
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
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <CheckCircle size={24} color="var(--green)" />
            <h2 style={{ margin: 0 }}>
              Found {result.transactions_found} transactions
            </h2>
          </div>
          <p style={{ color: "var(--text-dim)", marginBottom: 16 }}>
            Detected as: <span className="tag default">{result.file_type}</span>
          </p>

          {result.transactions.length > 0 && (
            <table>
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
                    <td>{t.date}</td>
                    <td>{t.description || "—"}</td>
                    <td><span className="tag default">{t.category}</span></td>
                    <td><span className="tag default">{t.payment_method.replace("_", " ")}</span></td>
                    <td style={{ textAlign: "right", fontWeight: 600 }}>{formatINR(t.amount)}</td>
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
        </div>
      )}

      {/* Upload History */}
      {history.length > 0 && (
        <div className="card">
          <h2>Upload History</h2>
          <table>
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
                  <td>{h.filename}</td>
                  <td><span className="tag default">{h.file_type}</span></td>
                  <td>{h.transactions_found}</td>
                  <td>{new Date(h.uploaded_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
