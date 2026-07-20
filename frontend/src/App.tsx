import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getReport, listFilings, runAudit, reportPdfUrl, type Report } from "./api";
import FilingList from "./components/FilingList";
import ScoreCard from "./components/ScoreCard";
import FindingsTable from "./components/FindingsTable";
import UploadForm from "./components/UploadForm";

export default function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [auditingId, setAuditingId] = useState<string | null>(null);
  const [showPdf, setShowPdf] = useState(false);
  const qc = useQueryClient();

  const { data: filings = [] } = useQuery({
    queryKey: ["filings"],
    queryFn: listFilings,
    refetchInterval: 3000, // live status: processing -> parsed -> indexed
  });

  async function handleRunAudit(filingId: string) {
    const filing = filings.find((f) => f.id === filingId);
    if (!filing || filing.status !== "indexed" || auditingId) return; // only one at a time
    setAuditingId(filingId);
    setReport(null);
    try {
      const { audit_run_id } = await runAudit(filing);
      for (let i = 0; i < 150; i++) {
        const r = await getReport(audit_run_id);
        if (r.status === "completed") {
          setReport(r);
          return;
        }
        await new Promise((res) => setTimeout(res, 2000));
      }
    } finally {
      setAuditingId(null);
    }
  }

  return (
    <div style={{ fontFamily: "system-ui", maxWidth: 1000, margin: "0 auto", padding: 24 }}>
      <h1>FinTech Corporate Compliance Auditor</h1>
      <UploadForm onUploaded={() => qc.invalidateQueries({ queryKey: ["filings"] })} />
      <FilingList filings={filings} onRunAudit={handleRunAudit} auditingId={auditingId} />
      {auditingId && <p>Auditing… deep reasoning can take ~30–60s. Please wait.</p>}
      {report && (
        <>
          <ScoreCard score={report.compliance_score} ticker={report.ticker} />
          <FindingsTable findings={report.findings} reportId={report.audit_run_id} />
          <button onClick={() => setShowPdf(true)} style={{ marginTop: 12 }}>
            View PDF report
          </button>
          {showPdf && (
            <div
              onClick={() => setShowPdf(false)}
              style={{
                position: "fixed",
                inset: 0,
                background: "rgba(0,0,0,0.6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 1000,
              }}
            >
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  width: "80%",
                  height: "90%",
                  background: "#fff",
                  borderRadius: 8,
                  overflow: "hidden",
                  position: "relative",
                }}
              >
                <button
                  onClick={() => setShowPdf(false)}
                  style={{ position: "absolute", top: 8, right: 8, zIndex: 1 }}
                >
                  Close
                </button>
                <iframe
                  title="report"
                  src={reportPdfUrl(report.audit_run_id)}
                  style={{ width: "100%", height: "100%", border: "none" }}
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
