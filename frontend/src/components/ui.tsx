export function SectionHeading({
  kicker,
  title,
  desc,
}: {
  kicker: string;
  title: string;
  desc?: string;
}) {
  return (
    <div className="section-head">
      <div className="kicker">{kicker}</div>
      <h2>{title}</h2>
      {desc && <p>{desc}</p>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="card">
      <div className="muted" style={{ fontSize: 12.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, margin: "6px 0 2px" }}>{value}</div>
      {sub && <div className="muted">{sub}</div>}
    </div>
  );
}

export function TriggerBadge({ type }: { type: string }) {
  const cls =
    type === "drought" ? "trig-drought" : type === "flood" ? "trig-flood" : "trig-earthquake";
  const label =
    type === "drought" ? "DROUGHT" : type === "flood" ? "FLOOD" : "EARTHQUAKE";
  return <span className={`trig ${cls}`}>{label}</span>;
}
