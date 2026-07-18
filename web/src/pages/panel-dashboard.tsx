import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AddCandidateDialog } from "../components/add-candidate-dialog";
import { AppShell } from "../components/app-shell";
import { MetricCard } from "../components/metric-card";
import { useAuth } from "../auth/use-auth";
import {
  createCandidate,
  listMyCandidates,
  type Candidate,
  type CandidateSubmissionInput,
  type JobStage,
  type Verdict,
} from "../lib/api";

const verdictLabels: Record<Verdict, string> = {
  selected: "Selected",
  not_decided: "Not decided",
  not_selected: "Not selected",
};

const stageLabels: Record<JobStage, string> = {
  uploaded: "Uploaded",
  queued: "Queued",
  transcribing: "Transcribing",
  transcribed: "Transcribed",
  analyzing: "Analyzing",
  completed: "Ready",
  failed: "Failed",
};

function CandidateRow({ candidate }: { candidate: Candidate }) {
  const status = candidate.stage ? stageLabels[candidate.stage] : "Awaiting recording";
  const statusTone = candidate.stage === "completed"
    ? "bg-mint text-moss"
    : candidate.stage === "failed"
      ? "bg-red-50 text-red-700"
      : "bg-amber-50 text-amber-800";

  return (
    <article className="grid gap-4 border-b border-ink/10 px-5 py-5 last:border-b-0 sm:grid-cols-[1fr_auto] sm:items-center sm:px-6">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="m-0 truncate text-base font-bold text-ink">{candidate.full_name}</h3>
          {candidate.external_id && <span className="rounded-md bg-fog px-2 py-1 text-xs font-semibold text-ink/50">{candidate.external_id}</span>}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink/50">
          <span>{new Date(candidate.created_at).toLocaleDateString()}</span>
          <span>{candidate.category === "ai_ml" ? "AI/ML" : candidate.category === "full_stack_engineer" ? "Full Stack Engineer" : "Category not assigned"}</span>
          <span>{candidate.verdict ? verdictLabels[candidate.verdict] : "Verdict pending"}</span>
          {candidate.overall_score !== null && <span className="font-bold text-moss">Score {candidate.overall_score.toFixed(1)}</span>}
        </div>
        {candidate.notes && <p className="mb-0 mt-2 line-clamp-2 text-sm text-ink/55">{candidate.notes}</p>}
      </div>
      <span className={`w-fit rounded-full px-3 py-1.5 text-xs font-bold ${statusTone}`}>{status}</span>
    </article>
  );
}

export function PanelDashboard() {
  const { user } = useAuth();
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const candidatesQuery = useQuery({
    queryKey: ["candidates", "mine"],
    queryFn: listMyCandidates,
    refetchInterval: 5000,
  });
  const createMutation = useMutation({
    mutationFn: createCandidate,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["candidates", "mine"] });
    },
  });

  const candidates = candidatesQuery.data ?? [];
  const processing = candidates.filter((candidate) => candidate.stage && !["completed", "failed"].includes(candidate.stage)).length;
  const ready = candidates.filter((candidate) => candidate.stage === "completed").length;

  function openDialog() {
    createMutation.reset();
    setDialogOpen(true);
  }

  async function submitCandidate(candidate: CandidateSubmissionInput) {
    await createMutation.mutateAsync(candidate);
  }

  return (
    <AppShell
      eyebrow="Panel workspace"
      title="My candidates"
      action={
        <button type="button" onClick={openDialog} className="rounded-xl bg-moss px-5 py-3 font-bold text-white shadow-lg shadow-moss/15 transition hover:bg-[#113d30]">
          + Add candidate
        </button>
      }
    >
      <section className="grid gap-4 sm:grid-cols-3">
        <MetricCard label="Interviews" value={String(candidates.length)} note="in this hiring round" accent />
        <MetricCard label="Processing" value={String(processing)} note="recordings in the queue" />
        <MetricCard label="Ready" value={String(ready)} note="evaluations available" />
      </section>

      {candidatesQuery.isPending ? (
        <section className="mt-6 rounded-2xl border border-ink/10 bg-white px-6 py-16 text-center text-sm font-semibold text-ink/45">Loading candidates…</section>
      ) : candidatesQuery.isError ? (
        <section className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-6 py-10 text-center">
          <p className="m-0 text-sm font-semibold text-red-800">{candidatesQuery.error.message}</p>
          <button type="button" onClick={() => void candidatesQuery.refetch()} className="mt-4 rounded-xl border border-red-300 px-4 py-2 text-sm font-bold text-red-800">Try again</button>
        </section>
      ) : candidates.length ? (
        <section className="mt-6 overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-lift">
          <div className="border-b border-ink/10 px-5 py-4 sm:px-6">
            <h2 className="display-font m-0 text-lg font-bold text-ink">Recent candidates</h2>
          </div>
          {candidates.map((candidate) => <CandidateRow key={candidate.id} candidate={candidate} />)}
        </section>
      ) : (
        <section className="mt-6 rounded-2xl border border-dashed border-ink/20 bg-white px-6 py-14 text-center sm:py-20">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-mint text-moss" aria-hidden="true">
            <svg viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="2"><path d="M12 5v14M5 12h14" strokeLinecap="round" /></svg>
          </span>
          <h2 className="display-font mb-2 mt-5 text-xl font-bold text-ink">Your first interview starts here</h2>
          <p className="mx-auto mb-5 max-w-md text-sm leading-6 text-ink/50">Add the candidate details and interview recording. Processing starts automatically after upload.</p>
          <button type="button" onClick={openDialog} className="rounded-xl bg-moss px-5 py-3 text-sm font-bold text-white">Add first candidate</button>
        </section>
      )}

      <AddCandidateDialog
        draftOwnerId={user?.id ?? "panel"}
        open={dialogOpen}
        pending={createMutation.isPending}
        error={createMutation.error?.message ?? null}
        onClose={() => setDialogOpen(false)}
        onSubmit={submitCandidate}
      />
    </AppShell>
  );
}
