import type { Filing } from "../api";

interface Props {
  filings: Filing[];
  onRunAudit: (filingId: string) => void;
  auditingId?: string | null;
}

const IN_PROGRESS = ["processing", "parsed", "embedding"];

function statusColor(status: string): string {
  if (status === "indexed") return "#137333"; // green
  if (status === "failed") return "#c5221f"; // red
  return "#8a6d00"; // amber (in-progress)
}

export default function FilingList({ filings, onRunAudit, auditingId = null }: Props) {
  const busy = auditingId !== null; // some audit is running

  return (
    <section>
      <h2>Filings</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={cell}>Ticker</th>
            <th style={cell}>Type</th>
            <th style={cell}>Period</th>
            <th style={cell}>Status</th>
            <th style={cell}>Action</th>
          </tr>
        </thead>
        <tbody>
          {filings.length === 0 && (
            <tr>
              <td style={cell} colSpan={5}>
                No filings yet — add one above.
              </td>
            </tr>
          )}
          {filings.map((f) => {
            const inProgress = IN_PROGRESS.includes(f.status);
            const ready = f.status === "indexed";
            const isAuditing = f.id === auditingId;
            return (
              <tr key={f.id}>
                <td style={cell}>{f.ticker}</td>
                <td style={cell}>{f.filing_type}</td>
                <td style={cell}>
                  {f.fiscal_quarter} FY{f.fiscal_year}
                </td>
                <td style={{ ...cell, color: statusColor(f.status), fontWeight: 600 }}>
                  {inProgress ? `${f.status}…` : f.status}
                </td>
                <td style={cell}>
                  <button
                    disabled={!ready || busy}
                    onClick={() => onRunAudit(f.id)}
                    title={ready ? "Run compliance audit" : `Waiting: ${f.status}`}
                  >
                    {isAuditing ? "Auditing…" : ready ? "Run Audit" : "Indexing…"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

const cell: React.CSSProperties = { border: "1px solid #ddd", padding: "6px 10px", textAlign: "left" };
