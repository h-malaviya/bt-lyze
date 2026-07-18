import type { AdminCandidate } from "../lib/api";
import {
  categoryLabels,
  recommendationLabels,
  recommendationTone,
  stageLabels,
  stageTone,
} from "../lib/admin-display";

interface AdminCandidateTableProps {
  candidates: AdminCandidate[];
  onSelect: (candidateId: string) => void;
}

export function AdminCandidateTable({ candidates, onSelect }: AdminCandidateTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] border-collapse text-left">
        <thead className="bg-fog text-xs uppercase tracking-[0.12em] text-ink/45">
          <tr>
            <th className="px-6 py-4 font-bold">Candidate</th>
            <th className="px-4 py-4 font-bold">Panel</th>
            <th className="px-4 py-4 font-bold">Stage</th>
            <th className="px-4 py-4 font-bold">Score</th>
            <th className="px-4 py-4 font-bold">Recommendation</th>
            <th className="px-4 py-4 font-bold">Submitted</th>
            <th className="px-6 py-4 text-right font-bold">Analysis</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr key={candidate.id} className="border-t border-ink/10 transition hover:bg-fog/60">
              <td className="px-6 py-4">
                <p className="m-0 font-bold text-ink">{candidate.full_name}</p>
                <p className="mb-0 mt-1 text-xs text-ink/45">
                  {candidate.external_id ?? "No candidate ID"}
                </p>
                <p className="mb-0 mt-1 text-xs font-semibold text-ink/55">
                  {candidate.category ? categoryLabels[candidate.category] : "Category not assigned"}
                </p>
              </td>
              <td className="px-4 py-4 text-sm font-semibold text-ink/65">{candidate.panel_name}</td>
              <td className="px-4 py-4">
                <span className={`inline-flex rounded-full px-3 py-1.5 text-xs font-bold ${stageTone(candidate.stage)}`}>
                  {candidate.stage ? stageLabels[candidate.stage] : "No recording"}
                </span>
              </td>
              <td className="px-4 py-4 text-sm font-bold text-moss">
                {candidate.overall_score === null ? "—" : candidate.overall_score.toFixed(1)}
              </td>
              <td className="px-4 py-4">
                {candidate.recommendation ? (
                  <span className={`inline-flex rounded-full px-3 py-1.5 text-xs font-bold ${recommendationTone(candidate.recommendation)}`}>
                    {recommendationLabels[candidate.recommendation]}
                  </span>
                ) : <span className="text-sm text-ink/35">Pending</span>}
              </td>
              <td className="px-4 py-4 text-sm text-ink/55">
                {new Date(candidate.created_at).toLocaleDateString()}
              </td>
              <td className="px-6 py-4 text-right">
                <button
                  type="button"
                  onClick={() => onSelect(candidate.id)}
                  className="rounded-lg border border-moss/20 bg-mint px-3 py-2 text-xs font-bold text-moss transition hover:border-moss/40"
                >
                  View details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
