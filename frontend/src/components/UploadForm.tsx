import { useRef, useState } from "react";
import { ingestFiling, ingestUrl } from "../api";

export default function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const [ticker, setTicker] = useState("");
  const [type, setType] = useState("10-K");
  const [year, setYear] = useState(new Date().getFullYear());
  const [quarter, setQuarter] = useState("FY");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  function removeFile() {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg("");

    // exactly one source
    if (file && url.trim()) {
      setMsg("Please provide only ONE source: a PDF file OR a URL, not both.");
      return;
    }
    if (!file && !url.trim()) {
      setMsg("Choose a PDF file or paste a URL.");
      return;
    }
    if (!ticker.trim()) {
      setMsg("Ticker is required.");
      return;
    }

    setBusy(true);
    try {
      if (file) {
        const fd = new FormData();
        fd.append("ticker", ticker.trim());
        fd.append("filing_type", type);
        fd.append("fiscal_year", String(year));
        fd.append("fiscal_quarter", quarter);
        fd.append("file", file);
        await ingestFiling(fd);
      } else {
        await ingestUrl({
          ticker: ticker.trim(),
          filing_type: type,
          fiscal_year: year,
          fiscal_quarter: quarter,
          url: url.trim(),
        });
      }
      setMsg("Uploaded — indexing. It will appear below shortly.");
      removeFile();
      setUrl("");
      onUploaded();
    } catch (err) {
      setMsg((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ border: "1px solid #ddd", padding: 16, borderRadius: 8, marginBottom: 24 }}>
      <h3>Add a filing</h3>
      <p style={{ margin: "0 0 8px", color: "#666", fontSize: 13 }}>
        Provide <strong>one</strong> source only — upload a PDF <em>or</em> paste a URL.
      </p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="Ticker" />
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="10-K">10-K</option>
          <option value="10-Q">10-Q</option>
        </select>
        <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
        <select value={quarter} onChange={(e) => setQuarter(e.target.value)}>
          <option value="FY">FY</option>
          <option value="Q1">Q1</option>
          <option value="Q2">Q2</option>
          <option value="Q3">Q3</option>
          <option value="Q4">Q4</option>
        </select>
      </div>

      <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
        <label>
          PDF:{" "}
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            disabled={!!url.trim()}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        {file && (
          <>
            <span style={{ fontSize: 13 }}>{file.name}</span>
            <button type="button" onClick={removeFile}>Remove</button>
          </>
        )}
      </div>

      <div style={{ marginTop: 8 }}>
        or URL:{" "}
        <input
          style={{ width: 420 }}
          value={url}
          disabled={!!file}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://.../report.pdf  or  SEC .htm URL"
        />
      </div>

      <button type="submit" disabled={busy} style={{ marginTop: 12 }}>
        {busy ? "Uploading…" : "Upload & index"}
      </button>
      {msg && <p style={{ marginTop: 8 }}>{msg}</p>}
    </form>
  );
}
