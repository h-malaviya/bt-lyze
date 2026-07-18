import { useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { AdminCandidateDetailDialog } from "../components/admin-candidate-detail-dialog";
import { AdminCandidateTable } from "../components/admin-candidate-table";
import { AppShell } from "../components/app-shell";
import { MetricCard } from "../components/metric-card";
import {
  listAdminCandidates,
  type JobStage,
  type Recommendation,
  type ScoreBand,
} from "../lib/api";

export function AdminDashboard() {
  const [search, setSearch] = useState("");
  const [panelId, setPanelId] = useState("");
  const [stage, setStage] = useState<JobStage | "">("");
  const [recommendation, setRecommendation] = useState<Recommendation | "">("");
  const [scoreBand, setScoreBand] = useState<ScoreBand | "">("");
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const deferredSearch = useDeferredValue(search);
  const candidatesQuery = useQuery({
    queryKey: ["admin-candidates", deferredSearch, panelId, stage, recommendation, scoreBand],
    queryFn: () => listAdminCandidates({
      ...(deferredSearch.trim() ? { search: deferredSearch } : {}),
      ...(panelId ? { panel_id: panelId } : {}),
      ...(stage ? { stage } : {}),
      ...(recommendation ? { recommendation } : {}),
      ...(scoreBand ? { score_band: scoreBand } : {}),
    }),
    refetchInterval: 5000,
  });

  const metrics = candidatesQuery.data?.metrics ?? {
    candidates: 0,
    ready: 0,
    in_progress: 0,
    needs_attention: 0,
  };
  const candidates = candidatesQuery.data?.items ?? [];
  const filtersActive = Boolean(search || panelId || stage || recommendation || scoreBand);

  function clearFilters() {
    setSearch("");
    setPanelId("");
    setStage("");
    setRecommendation("");
    setScoreBand("");
  }

  return (
    <AppShell
      eyebrow="Hiring overview"
      title="Candidate intelligence"
      action={<button type="button" disabled className="rounded-xl border border-ink/15 bg-white px-5 py-3 font-bold text-ink opacity-50">Export view</button>}
    >
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Candidates" value={String(metrics.candidates)} note="across all panels" accent />
        <MetricCard label="Ready" value={String(metrics.ready)} note="fully evaluated" />
        <MetricCard label="In progress" value={String(metrics.in_progress)} note="being processed" />
        <MetricCard label="Needs attention" value={String(metrics.needs_attention)} note="failed or awaiting recording" />
      </section>

      <section className="mt-6 overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-lift">
        <div className="grid gap-3 border-b border-ink/10 p-4 lg:grid-cols-[minmax(220px,1fr)_200px_170px_180px_160px_auto]">
          <label className="sr-only" htmlFor="admin-search">Search candidates</label>
          <input id="admin-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search candidates, IDs, notes…" className="rounded-xl border border-ink/10 bg-fog px-4 py-3 text-sm outline-none focus:border-moss focus:ring-4 focus:ring-mint" />
          <label className="sr-only" htmlFor="admin-panel-filter">Filter by panel</label>
          <select id="admin-panel-filter" value={panelId} onChange={(event) => setPanelId(event.target.value)} className="rounded-xl border border-ink/10 bg-white px-4 py-3 text-sm text-ink/65 outline-none focus:border-moss">
            <option value="">All panels</option>
            {candidatesQuery.data?.panels.map((panel) => <option key={panel.id} value={panel.id}>{panel.name}</option>)}
          </select>
          <label className="sr-only" htmlFor="admin-stage-filter">Filter by stage</label>
          <select id="admin-stage-filter" value={stage} onChange={(event) => setStage(event.target.value as JobStage | "")} className="rounded-xl border border-ink/10 bg-white px-4 py-3 text-sm text-ink/65 outline-none focus:border-moss">
            <option value="">All stages</option>
            <option value="queued">Queued</option>
            <option value="transcribing">Transcribing</option>
            <option value="transcribed">Transcribed</option>
            <option value="analyzing">Analyzing</option>
            <option value="completed">Ready</option>
            <option value="failed">Failed</option>
          </select>
          <label className="sr-only" htmlFor="admin-recommendation-filter">Filter by recommendation</label>
          <select id="admin-recommendation-filter" value={recommendation} onChange={(event) => setRecommendation(event.target.value as Recommendation | "")} className="rounded-xl border border-ink/10 bg-white px-4 py-3 text-sm text-ink/65 outline-none focus:border-moss">
            <option value="">All recommendations</option>
            <option value="selected">Selected</option>
            <option value="borderline">Borderline</option>
            <option value="not_selected">Not selected</option>
          </select>
          <label className="sr-only" htmlFor="admin-score-filter">Filter by overall score</label>
          <select id="admin-score-filter" value={scoreBand} onChange={(event) => setScoreBand(event.target.value as ScoreBand | "")} className="rounded-xl border border-ink/10 bg-white px-4 py-3 text-sm text-ink/65 outline-none focus:border-moss">
            <option value="">All scores</option>
            <option value="4_to_5">4–5</option>
            <option value="3">3</option>
            <option value="1_to_2">1–2</option>
            <option value="unscored">Not scored</option>
          </select>
          <button type="button" onClick={clearFilters} disabled={!filtersActive} className="rounded-xl border border-ink/10 px-4 py-3 text-sm font-bold text-ink/60 transition hover:bg-fog disabled:opacity-35">Clear</button>
        </div>

        {candidatesQuery.isPending ? (
          <div className="px-6 py-20 text-center text-sm font-semibold text-ink/45">Loading candidate intelligence…</div>
        ) : candidatesQuery.isError ? (
          <div className="px-6 py-16 text-center">
            <p className="m-0 text-sm font-semibold text-red-800">{candidatesQuery.error.message}</p>
            <button type="button" onClick={() => void candidatesQuery.refetch()} className="mt-4 rounded-xl border border-red-300 px-4 py-2 text-sm font-bold text-red-800">Try again</button>
          </div>
        ) : candidates.length ? (
          <>
            <div className="flex items-center justify-between border-b border-ink/10 px-6 py-3 text-xs font-semibold text-ink/45">
              <span>Showing {candidates.length} of {candidatesQuery.data.total}</span>
              <span>Updates every 5 seconds</span>
            </div>
            <AdminCandidateTable candidates={candidates} onSelect={setSelectedCandidateId} />
          </>
        ) : (
          <div className="px-6 py-20 text-center">
            <h2 className="display-font m-0 text-xl font-bold text-ink">No matching candidates</h2>
            <p className="mx-auto mb-0 mt-2 max-w-md text-sm leading-6 text-ink/50">
              {filtersActive ? "Clear or adjust the filters to see more interviews." : "Candidates will appear as panels submit recordings."}
            </p>
          </div>
        )}
      </section>

      <AdminCandidateDetailDialog candidateId={selectedCandidateId} onClose={() => setSelectedCandidateId(null)} />
    </AppShell>
  );
}
