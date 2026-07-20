interface Props {
  score: number | null;
  ticker: string;
}

function color(score: number): string {
  if (score >= 80) return "#15803d";
  if (score >= 50) return "#a16207";
  return "#b91c1c";
}

export default function ScoreCard({ score, ticker }: Props) {
  const s = score ?? 0;
  return (
    <section style={{ margin: "24px 0", padding: 16, border: "1px solid #ddd", borderRadius: 8 }}>
      <h2 style={{ margin: 0 }}>Compliance Score — {ticker}</h2>
      <div style={{ fontSize: 48, fontWeight: 700, color: color(s) }}>{s}</div>
    </section>
  );
}
