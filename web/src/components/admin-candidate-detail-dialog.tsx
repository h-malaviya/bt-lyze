import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  getAdminCandidate,
  getAdminRecordingPlayback,
  type AdminCandidateDetail,
} from "../lib/api";
import {
  categoryLabels,
  formatBytes,
  formatDuration,
  recommendationLabels,
  recommendationTone,
  stageLabels,
  stageTone,
  verdictLabels,
} from "../lib/admin-display";

interface AdminCandidateDetailDialogProps {
  candidateId: string | null;
  onClose: () => void;
}

const maximumSectionPoints = 4;
const markdownBulletPrefix = /^[-*\u2022\u2013\u2014]\s+/;

function sectionPoints(content: string): string[] {
  const normalizedContent = content.replaceAll("\\n", "\n").trim();
  const markdownPoints = normalizedContent
    .split(/\r?\n|(?=\s+[-*\u2022\u2013\u2014]\s+)/)
    .map((point) => point.trim().replace(markdownBulletPrefix, ""))
    .filter(Boolean);
  const points = markdownPoints.length > 1
    ? markdownPoints
    : normalizedContent.match(/[^.!?]+(?:[.!?]+|$)/g) ?? [];

  return points
    .map((point) => point.trim().replace(markdownBulletPrefix, ""))
    .filter(Boolean)
    .slice(0, maximumSectionPoints);
}

function itemPoints(items: string[]): string[] {
  return items
    .flatMap(sectionPoints)
    .slice(0, maximumSectionPoints);
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="mb-0 mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-ink/65 marker:text-moss">
      {items.map((point, index) => <li key={`${index}-${point}`}>{point}</li>)}
    </ul>
  );
}

function categoryTitle(category: string): string {
  return category
    .trim()
    .replaceAll("_", " ");
}

function EvaluationView({ candidate }: { candidate: AdminCandidateDetail }) {
  const evaluation = candidate.evaluation;
  if (!evaluation) {
    return (
      <section className="rounded-2xl border border-dashed border-ink/15 bg-fog px-5 py-8 text-center">
        <p className="m-0 text-sm font-semibold text-ink/50">
          Analysis will appear here when processing completes.
        </p>
      </section>
    );
  }
  const summary = sectionPoints(evaluation.summary);

  return (
    <div className="space-y-5">
      <section className="grid gap-4 rounded-2xl bg-moss p-5 text-white sm:grid-cols-[auto_1fr] sm:items-center">
        <div>
          <p className="m-0 text-xs font-bold uppercase tracking-[0.16em] text-white/60">Overall score</p>
          <p className="display-font mb-0 mt-1 text-4xl font-bold">
            {evaluation.overall_score === null
              ? "—"
              : `${Math.round(evaluation.overall_score)}/5`}
          </p>
        </div>
        <div className="sm:text-right">
          {evaluation.recommendation && (
            <span className={`inline-flex rounded-full px-3 py-1.5 text-xs font-bold ${recommendationTone(evaluation.recommendation)}`}>
              {recommendationLabels[evaluation.recommendation]}
            </span>
          )}
          <p className="mb-0 mt-2 text-xs text-white/60">
            {evaluation.model ?? "Unknown model"} · {evaluation.prompt_version}
          </p>
        </div>
      </section>

      <section>
        <h3 className="mb-3 mt-0 text-base font-bold text-ink">Category evidence</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(evaluation.scores).map(([category, score]) => (
            <article key={category} className="rounded-2xl border border-ink/10 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <h4 className="m-0 capitalize text-sm font-bold text-ink">{categoryTitle(category)}</h4>
                <span className="text-lg font-bold text-moss">{Math.round(score.score)}/5</span>
              </div>
              <BulletList items={sectionPoints(score.rationale)} />
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-ink/10 bg-fog p-5">
        <h3 className="m-0 text-base font-bold text-ink">Summary</h3>
        <BulletList items={summary} />
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <EvidenceList title="Strengths" items={evaluation.strengths} tone="text-emerald-700" />
        <EvidenceList title="Concerns" items={evaluation.concerns} tone="text-red-700" />
      </section>

      {evaluation.token_usage && (
        <section className="rounded-2xl border border-ink/10 bg-white p-5">
          <h3 className="m-0 text-base font-bold text-ink">Token usage</h3>
          <dl className="mb-0 mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <TokenMetric label="Input" value={evaluation.token_usage.input_tokens} />
            <TokenMetric label="Output" value={evaluation.token_usage.output_tokens} />
            <TokenMetric label="Cache write" value={evaluation.token_usage.cache_creation_input_tokens} />
            <TokenMetric label="Cache read" value={evaluation.token_usage.cache_read_input_tokens} />
          </dl>
        </section>
      )}
    </div>
  );
}

function TokenMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-fog p-3">
      <dt className="text-xs font-semibold text-ink/45">{label}</dt>
      <dd className="mb-0 ml-0 mt-1 font-bold text-ink">{value.toLocaleString()}</dd>
    </div>
  );
}

function EvidenceList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  const points = itemPoints(items);

  return (
    <article className="rounded-2xl border border-ink/10 bg-white p-5">
      <h3 className={`m-0 text-base font-bold ${tone}`}>{title}</h3>
      {points.length ? (
        <BulletList items={points} />
      ) : <p className="mb-0 mt-3 text-sm text-ink/40">None recorded</p>}
    </article>
  );
}

function RecordingView({ candidate }: { candidate: AdminCandidateDetail }) {
  const recording = candidate.recording;
  const playbackQuery = useQuery({
    queryKey: ["admin-recording-playback", recording?.id],
    queryFn: () => getAdminRecordingPlayback(recording!.id),
    enabled: Boolean(recording),
    staleTime: 60 * 60 * 1000,
  });
  if (!recording) return <p className="text-sm text-ink/45">No recording attached.</p>;
  return (
    <section className="rounded-2xl border border-ink/10 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="m-0 text-base font-bold text-ink">{recording.original_filename ?? "Interview recording"}</h3>
          <p className="mb-0 mt-1 text-xs font-semibold capitalize text-ink/45">
            {recording.storage_provider} storage · {recording.storage_container}
          </p>
          <p className="mb-0 mt-1 text-xs text-ink/45">
            {formatBytes(recording.size_bytes)} · {formatDuration(recording.duration_sec)} · attempt {recording.attempt_count}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1.5 text-xs font-bold ${stageTone(recording.stage)}`}>
          {stageLabels[recording.stage]}
        </span>
      </div>
      {recording.last_error && (
        <p className="mb-0 mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {recording.last_error}
        </p>
      )}
      <div className="mt-5 border-t border-ink/10 pt-5">
        <p className="mb-2 mt-0 text-xs font-bold uppercase tracking-[0.12em] text-ink/45">
          Listen to interview
        </p>
        {playbackQuery.isPending ? (
          <p className="m-0 text-sm font-semibold text-ink/45">Preparing audio player...</p>
        ) : playbackQuery.isError ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="m-0 text-sm font-semibold text-red-700">
              {playbackQuery.error.message}
            </p>
            <button
              type="button"
              onClick={() => void playbackQuery.refetch()}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-bold text-red-700 hover:bg-red-50"
            >
              Try again
            </button>
          </div>
        ) : (
          <audio
            controls
            preload="metadata"
            src={playbackQuery.data.url}
            aria-label={`Interview recording for ${candidate.full_name}`}
            className="block h-11 w-full"
          >
            Your browser does not support audio playback.
          </audio>
        )}
      </div>
    </section>
  );
}

export function AdminCandidateDetailDialog({ candidateId, onClose }: AdminCandidateDetailDialogProps) {
  const detailQuery = useQuery({
    queryKey: ["admin-candidate", candidateId],
    queryFn: () => getAdminCandidate(candidateId!),
    enabled: Boolean(candidateId),
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (!candidateId) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [candidateId, onClose]);

  if (!candidateId) return null;
  const candidate = detailQuery.data;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/45 backdrop-blur-sm">
      <section role="dialog" aria-modal="true" aria-labelledby="candidate-analysis-title" className="h-full w-full max-w-5xl overflow-y-auto bg-fog shadow-2xl">
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-ink/10 bg-white/95 px-5 py-5 backdrop-blur sm:px-8">
          <div>
            <p className="m-0 text-xs font-bold uppercase tracking-[0.16em] text-ember">Candidate analysis</p>
            <h2 id="candidate-analysis-title" className="display-font mb-0 mt-1 text-2xl font-bold text-ink">
              {candidate?.full_name ?? "Loading…"}
            </h2>
            {candidate && <p className="mb-0 mt-1 text-sm text-ink/50">{candidate.panel_name} · {candidate.external_id ?? "No candidate ID"}</p>}
          </div>
          <button type="button" onClick={onClose} aria-label="Close analysis" className="grid h-10 w-10 place-items-center rounded-xl border border-ink/10 bg-white text-xl text-ink/60 hover:bg-fog">×</button>
        </header>

        {detailQuery.isPending ? (
          <div className="px-8 py-24 text-center text-sm font-semibold text-ink/45">Loading analysis…</div>
        ) : detailQuery.isError ? (
          <div className="m-6 rounded-2xl border border-red-200 bg-red-50 p-6 text-center sm:m-8">
            <p className="m-0 text-sm font-semibold text-red-800">{detailQuery.error.message}</p>
            <button type="button" onClick={() => void detailQuery.refetch()} className="mt-4 rounded-xl border border-red-300 px-4 py-2 text-sm font-bold text-red-800">Try again</button>
          </div>
        ) : candidate ? (
          <div className="space-y-6 p-5 sm:p-8">
            <section className="flex flex-wrap gap-2 text-xs font-semibold text-ink/55">
              <span className="rounded-full bg-white px-3 py-1.5">Submitted {new Date(candidate.created_at).toLocaleString()}</span>
              <span className="rounded-full bg-white px-3 py-1.5">Category: {candidate.category ? categoryLabels[candidate.category] : "Not assigned"}</span>
              <span className="rounded-full bg-white px-3 py-1.5">Panel verdict: {candidate.verdict ? verdictLabels[candidate.verdict] : "Pending"}</span>
            </section>
            {candidate.notes && <section className="rounded-2xl border border-ink/10 bg-white p-5"><h3 className="m-0 text-base font-bold text-ink">Panel notes</h3><p className="mb-0 mt-3 whitespace-pre-wrap text-sm leading-6 text-ink/65">{candidate.notes}</p></section>}
            <RecordingView candidate={candidate} />
            <EvaluationView candidate={candidate} />
            <section className="rounded-2xl border border-ink/10 bg-white p-5">
              <h3 className="m-0 text-base font-bold text-ink">Transcript</h3>
              <pre className="mb-0 mt-4 max-h-[420px] overflow-y-auto whitespace-pre-wrap rounded-xl bg-ink p-4 font-sans text-sm leading-6 text-white/80">{candidate.transcript?.text ?? "Transcript is not available yet."}</pre>
            </section>
            <section className="rounded-2xl border border-ink/10 bg-white p-5">
              <h3 className="m-0 text-base font-bold text-ink">Processing history</h3>
              <div className="mt-4 space-y-3">
                {candidate.events.map((event) => (
                  <div key={event.id} className="grid gap-1 border-l-2 border-moss/25 pl-4 text-sm sm:grid-cols-[150px_1fr]">
                    <span className="font-bold capitalize text-ink">{event.stage ? stageLabels[event.stage] : "System"} · {event.status}</span>
                    <span className="text-ink/55">{event.detail ?? "No detail"} · {new Date(event.created_at).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        ) : null}
      </section>
    </div>
  );
}
