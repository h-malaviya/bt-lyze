import type { CandidateCategory, JobStage, Recommendation, Verdict } from "./api";

export const categoryLabels: Record<CandidateCategory, string> = {
  ai_ml: "AI/ML",
  full_stack_engineer: "Full Stack Engineer",
};

export const stageLabels: Record<JobStage, string> = {
  uploaded: "Uploaded",
  queued: "Queued",
  transcribing: "Transcribing",
  transcribed: "Transcribed",
  analyzing: "Analyzing",
  completed: "Ready",
  failed: "Failed",
};

export const recommendationLabels: Record<Recommendation, string> = {
  selected: "Selected",
  not_selected: "Not selected",
  borderline: "Borderline",
};

export const verdictLabels: Record<Verdict, string> = {
  selected: "Selected",
  not_decided: "Not decided",
  not_selected: "Not selected",
};

export function stageTone(stage: JobStage | null): string {
  if (stage === "completed") return "bg-mint text-moss";
  if (stage === "failed") return "bg-red-50 text-red-700";
  if (!stage) return "bg-slate-100 text-slate-600";
  return "bg-amber-50 text-amber-800";
}

export function recommendationTone(recommendation: Recommendation | null): string {
  if (recommendation === "selected") return "bg-emerald-50 text-emerald-700";
  if (recommendation === "not_selected") return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-800";
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "Unknown size";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "Unknown duration";
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}
