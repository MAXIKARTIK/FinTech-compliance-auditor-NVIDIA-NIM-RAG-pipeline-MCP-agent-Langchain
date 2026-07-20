const BASE = "/api";
const API_KEY = import.meta.env.VITE_API_KEY ?? "change-me";

const authHeaders = { "X-API-Key": API_KEY };

export interface Filing {
  id: string;
  ticker: string;
  filing_type: string;
  fiscal_year: number;
  fiscal_quarter: string;
  status: string;
}

export interface Evidence {
  chunk_id: string;
  quote: string;
}
export async function ingestFiling(form: FormData) {
  const res = await fetch(`/api/filings/ingest`, {
    method: "POST", headers: { "X-API-Key": API_KEY }, body: form });
  if (!res.ok) throw new Error(`ingest failed (${res.status})`);
  return res.json();
}

export async function ingestUrl(body: {
  ticker: string; filing_type: string; fiscal_year: number; fiscal_quarter: string; url: string;
}) {
  const res = await fetch(`/api/filings/ingest-url`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`ingest failed (${res.status})`);
  return res.json();
}

export interface Finding {
  rule_id: string;
  status: string;
  severity: string;
  confidence: number;
  explanation: string;
  evidence: Evidence[];
}

export interface Report {
  audit_run_id: string;
  ticker: string;
  filing_type: string;
  fiscal_year: number;
  fiscal_quarter: string;
  status: string;
  compliance_score: number | null;
  findings: Finding[];
}

export async function listFilings(): Promise<Filing[]> {
  const r = await fetch(`${BASE}/filings`);
  if (!r.ok) throw new Error("failed to list filings");
  return r.json();
}

export async function runAudit(f: Filing): Promise<{ audit_run_id: string }> {
  const r = await fetch(`${BASE}/audit/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders },
    body: JSON.stringify({
      ticker: f.ticker,
      filing_type: f.filing_type,
      fiscal_year: f.fiscal_year,
      fiscal_quarter: f.fiscal_quarter,
    }),
  });
  if (!r.ok) throw new Error("failed to start audit");
  return r.json();
}

export async function getReport(runId: string): Promise<Report> {
  const r = await fetch(`${BASE}/audit/report/${runId}`);
  if (!r.ok) throw new Error("failed to load report");
  return r.json();
}

export function reportPdfUrl(runId: string): string {
  return `${BASE}/audit/report/${runId}/pdf`;
}
