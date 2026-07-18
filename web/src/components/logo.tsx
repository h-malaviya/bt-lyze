export function Logo({ inverse = false }: { inverse?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={`grid h-10 w-10 place-items-center rounded-xl ${inverse ? "bg-white/10" : "bg-moss"}`}
        aria-hidden="true"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-white" strokeWidth="2">
          <path d="M6 8.5h12M6 12h8M6 15.5h5" strokeLinecap="round" />
          <path d="M4 4h16v16H8l-4-4V4Z" strokeLinejoin="round" />
        </svg>
      </span>
      <div>
        <div className={`display-font text-lg font-bold tracking-tight ${inverse ? "text-white" : "text-ink"}`}>
          Intervue
        </div>
        <div className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${inverse ? "text-white/50" : "text-ink/45"}`}>
          evaluation desk
        </div>
      </div>
    </div>
  );
}
