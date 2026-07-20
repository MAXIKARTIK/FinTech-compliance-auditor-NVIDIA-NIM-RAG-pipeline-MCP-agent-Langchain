import { Fragment, useState } from "react";
import { reportPdfUrl, type Finding } from "../api";

interface Props {
  findings: Finding[];
  reportId: string;
}

const SEVERITY_COLOR: Record<string, string> = {
  Critical: "#b91c1c",
  High: "#c2410c",
  Medium: "#a16207",
  Low: "#15803d",
};

export default function FindingsTable({ findings, reportId }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <section>
      <h2>
        Findings{" "}
        <a href={reportPdfUrl(reportId)} target="_blank" rel="noreferrer">
          (Download PDF)
        </a>
      </h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={cell}>Rule</th>
            <th style={cell}>Status</th>
            <th style={cell}>Severity</th>
            <th style={cell}>Confidence</th>
            <th style={cell}>Explanation</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f) => (
            <Fragment key={f.rule_id}>
              <tr
                onClick={() => setOpen(open === f.rule_id ? null : f.rule_id)}
                style={{ cursor: "pointer" }}
              >
                <td style={cell}>{f.rule_id}</td>
                <td style={cell}>{f.status}</td>
                <td style={{ ...cell, color: SEVERITY_COLOR[f.severity], fontWeight: 600 }}>
                  {f.severity}
                </td>
                <td style={cell}>{f.confidence.toFixed(2)}</td>
                <td style={cell}>{f.explanation}</td>
              </tr>
              {open === f.rule_id && (
                <tr key={f.rule_id + "-ev"}>
                  <td style={cell} colSpan={5}>
                    <strong>Evidence</strong>
                    <ul>
                      {f.evidence.map((e, i) => (
                        <li key={`${e.chunk_id}-${i}`}>
                          <em>[{e.chunk_id}]</em> {e.quote}
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </section>
  );
}

const cell: React.CSSProperties = { border: "1px solid #ddd", padding: "6px 10px", textAlign: "left" };
