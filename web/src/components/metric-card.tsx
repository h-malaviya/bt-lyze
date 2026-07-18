interface MetricCardProps {
  label: string;
  value: string;
  note: string;
  accent?: boolean;
}

export function MetricCard({ label, value, note, accent = false }: MetricCardProps) {
  return (
    <article className={`rounded-2xl border p-5 shadow-lift ${accent ? "border-moss bg-moss text-white" : "border-ink/10 bg-white text-ink"}`}>
      <p className={`m-0 text-xs font-bold uppercase tracking-[0.14em] ${accent ? "text-white/60" : "text-ink/45"}`}>{label}</p>
      <p className="display-font mb-1 mt-4 text-3xl font-bold">{value}</p>
      <p className={`m-0 text-sm ${accent ? "text-white/65" : "text-ink/50"}`}>{note}</p>
    </article>
  );
}
