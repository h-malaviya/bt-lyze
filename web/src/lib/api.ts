import { supabase, supabaseAnonKey, supabaseUrl } from "./supabase";

export type Role = "admin" | "panel";
export type Verdict = "selected" | "not_decided" | "not_selected";
export type CandidateCategory = "ai_ml" | "full_stack_engineer";
export type JobStage =
  | "uploaded"
  | "queued"
  | "transcribing"
  | "transcribed"
  | "analyzing"
  | "completed"
  | "failed";
export type Recommendation = "selected" | "not_selected" | "borderline";
export type StorageProvider = "supabase" | "azure";
export type ScoreBand = "4_to_5" | "3" | "1_to_2" | "unscored";

export interface CurrentUser {
  id: string;
  email: string | null;
  role: Role;
  panel_id: string | null;
  full_name: string | null;
}

interface MeResponse {
  user: CurrentUser;
}

interface ApiErrorEnvelope {
  error?: { message?: string };
  detail?: string | Array<{ msg?: string }>;
}

export interface Candidate {
  id: string;
  external_id: string | null;
  full_name: string;
  category: CandidateCategory | null;
  panel_id: string;
  panel_name: string;
  verdict: Verdict | null;
  notes: string | null;
  recording_id: string | null;
  stage: JobStage | null;
  overall_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateInput {
  full_name: string;
  external_id: string;
  category: CandidateCategory;
  verdict: Verdict;
  notes?: string;
}

export interface AdminMetrics {
  candidates: number;
  ready: number;
  in_progress: number;
  needs_attention: number;
}

export interface PanelOption {
  id: string;
  name: string;
}

export interface AdminCandidate {
  id: string;
  external_id: string | null;
  full_name: string;
  category: CandidateCategory | null;
  panel_id: string;
  panel_name: string;
  verdict: Verdict | null;
  recording_id: string | null;
  stage: JobStage | null;
  overall_score: number | null;
  recommendation: Recommendation | null;
  created_at: string;
  updated_at: string;
}

export interface EvaluationCategory {
  score: number;
  rationale: string;
}

export interface AdminCandidateDetail {
  id: string;
  external_id: string | null;
  full_name: string;
  category: CandidateCategory | null;
  panel_id: string;
  panel_name: string;
  verdict: Verdict | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  recording: {
    id: string;
    storage_provider: StorageProvider;
    storage_container: string;
    original_filename: string | null;
    duration_sec: number | null;
    size_bytes: number | null;
    mime_type: string | null;
    stage: JobStage;
    attempt_count: number;
    last_error: string | null;
    created_at: string;
    updated_at: string;
  } | null;
  transcript: {
    text: string | null;
    language: string | null;
    created_at: string;
  } | null;
  evaluation: {
    version: number;
    overall_score: number | null;
    scores: Record<string, EvaluationCategory>;
    summary: string;
    strengths: string[];
    concerns: string[];
    recommendation: Recommendation | null;
    prompt_version: string;
    model: string | null;
    token_usage: {
      input_tokens: number;
      output_tokens: number;
      cache_creation_input_tokens: number;
      cache_read_input_tokens: number;
      total_input_tokens: number;
      cache_hit: boolean;
      total_cost_usd: number | null;
    } | null;
    created_at: string;
  } | null;
  events: Array<{
    id: number;
    stage: JobStage | null;
    status: "started" | "succeeded" | "failed" | "retry";
    detail: string | null;
    created_at: string;
  }>;
}

export interface AdminCandidateFilters {
  search?: string;
  panel_id?: string;
  stage?: JobStage;
  recommendation?: Recommendation;
  score_band?: ScoreBand;
}

export interface AdminRecordingPlayback {
  url: string;
  expires_at: string;
}

export interface AdminCandidateListResponse {
  items: AdminCandidate[];
  total: number;
  metrics: AdminMetrics;
  panels: PanelOption[];
}

export interface UploadedRecording {
  storage_provider: StorageProvider;
  storage_container: string;
  storage_path: string;
  original_filename: string;
  size_bytes: number;
  mime_type: string | null;
}

export interface CandidateSubmissionInput extends CandidateInput {
  recording: UploadedRecording;
}

interface RecordingUploadGrant {
  storage_provider: StorageProvider;
  storage_container: string;
  storage_path: string;
  upload_url: string | null;
  upload_headers: Record<string, string>;
  expires_at: string | null;
}

interface CandidateListResponse {
  items: Candidate[];
  total: number;
}

async function errorMessage(response: Response): Promise<string> {
  const body = (await response.json().catch(() => ({}))) as ApiErrorEnvelope;
  if (body.error?.message) return body.error.message;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  return "Something went wrong. Please try again.";
}

async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  if (!supabase) throw new Error("Supabase is not configured");
  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new Error("Your session has expired. Please sign in again.");

  const response = await fetch(path, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${data.session.access_token}`,
    },
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response;
}

export async function getCurrentUser(accessToken: string): Promise<CurrentUser> {
  const response = await fetch("/api/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorEnvelope;
    throw new Error(body.error?.message ?? "Could not load your account");
  }

  return ((await response.json()) as MeResponse).user;
}

export async function listMyCandidates(): Promise<Candidate[]> {
  const response = await authorizedFetch("/api/candidates?scope=mine");
  return ((await response.json()) as CandidateListResponse).items;
}

export async function listAdminCandidates(
  filters: AdminCandidateFilters,
): Promise<AdminCandidateListResponse> {
  const parameters = new URLSearchParams();
  if (filters.search?.trim()) parameters.set("search", filters.search.trim());
  if (filters.panel_id) parameters.set("panel_id", filters.panel_id);
  if (filters.stage) parameters.set("stage", filters.stage);
  if (filters.recommendation) parameters.set("recommendation", filters.recommendation);
  if (filters.score_band) parameters.set("score_band", filters.score_band);
  parameters.set("limit", "200");
  const response = await authorizedFetch(`/api/admin/candidates?${parameters.toString()}`);
  return (await response.json()) as AdminCandidateListResponse;
}

export async function getAdminCandidate(candidateId: string): Promise<AdminCandidateDetail> {
  const response = await authorizedFetch(`/api/admin/candidates/${candidateId}`);
  return (await response.json()) as AdminCandidateDetail;
}

export async function getAdminRecordingPlayback(
  recordingId: string,
): Promise<AdminRecordingPlayback> {
  const response = await authorizedFetch(`/api/admin/recordings/${recordingId}/playback`);
  return (await response.json()) as AdminRecordingPlayback;
}

const maximumRecordingBytes = 500 * 1024 * 1024;

async function requestRecordingUpload(
  candidateName: string,
  recording: File,
): Promise<RecordingUploadGrant> {
  const response = await authorizedFetch("/api/recordings/upload-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_name: candidateName,
      original_filename: recording.name,
      size_bytes: recording.size,
      mime_type: recording.type || null,
    }),
  });
  return (await response.json()) as RecordingUploadGrant;
}

function encodedStoragePath(storagePath: string): string {
  return storagePath.split("/").map(encodeURIComponent).join("/");
}

async function uploadRecordingWithProgress(
  grant: RecordingUploadGrant,
  recording: File,
  onProgress: (percentage: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  const { data } = await supabase!.auth.getSession();
  if (!data.session) throw new Error("Your session has expired. Please sign in again.");

  let method: "POST" | "PUT";
  let uploadUrl: string;
  let headers: Record<string, string>;
  if (grant.storage_provider === "azure") {
    if (!grant.upload_url) throw new Error("Azure did not provide an upload URL");
    method = "PUT";
    uploadUrl = grant.upload_url;
    headers = grant.upload_headers;
  } else {
    if (!supabaseUrl || !supabaseAnonKey) throw new Error("Supabase is not configured");
    method = "POST";
    uploadUrl = `${supabaseUrl}/storage/v1/object/${encodeURIComponent(grant.storage_container)}/${encodedStoragePath(grant.storage_path)}`;
    headers = {
      apikey: supabaseAnonKey,
      Authorization: `Bearer ${data.session.access_token}`,
      "x-upsert": "false",
    };
  }

  await new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    const abortRequest = () => request.abort();
    request.open(method, uploadUrl);
    Object.entries(headers).forEach(([name, value]) => request.setRequestHeader(name, value));
    request.setRequestHeader("Content-Type", recording.type || "application/octet-stream");
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
      }
    });
    request.addEventListener("load", () => {
      signal?.removeEventListener("abort", abortRequest);
      if (request.status >= 200 && request.status < 300) {
        onProgress(100);
        resolve();
      } else {
        reject(new Error(`Recording upload failed (${request.status})`));
      }
    });
    request.addEventListener("error", () => {
      signal?.removeEventListener("abort", abortRequest);
      reject(new Error("Recording upload failed because of a network error"));
    });
    request.addEventListener("abort", () => {
      signal?.removeEventListener("abort", abortRequest);
      reject(new DOMException("Recording upload cancelled", "AbortError"));
    });
    signal?.addEventListener("abort", abortRequest, { once: true });
    if (signal?.aborted) {
      request.abort();
      return;
    }
    request.send(recording);
  });
}

export async function cleanupRecordingUpload(
  recording: UploadedRecording,
): Promise<void> {
  if (recording.storage_provider === "azure") {
    await authorizedFetch("/api/recordings/upload", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        storage_provider: recording.storage_provider,
        storage_container: recording.storage_container,
        storage_path: recording.storage_path,
      }),
    });
    return;
  }
  if (!supabase) throw new Error("Supabase is not configured");
  const cleanup = await supabase.storage
    .from(recording.storage_container)
    .remove([recording.storage_path]);
  if (cleanup.error) throw new Error(cleanup.error.message);
}

export async function uploadCandidateRecording(
  candidateName: string,
  recording: File,
  onProgress: (percentage: number) => void,
  signal?: AbortSignal,
): Promise<UploadedRecording> {
  if (!supabase) throw new Error("Supabase is not configured");
  if (recording.size > maximumRecordingBytes) {
    throw new Error("The recording must be 500 MB or smaller.");
  }
  const grant = await requestRecordingUpload(candidateName, recording);
  try {
    await uploadRecordingWithProgress(grant, recording, onProgress, signal);
  } catch (error) {
    const uploadedRecording: UploadedRecording = {
      storage_provider: grant.storage_provider,
      storage_container: grant.storage_container,
      storage_path: grant.storage_path,
      original_filename: recording.name,
      size_bytes: recording.size,
      mime_type: recording.type || null,
    };
    void cleanupRecordingUpload(uploadedRecording).catch(() => undefined);
    throw error;
  }
  return {
    storage_provider: grant.storage_provider,
    storage_container: grant.storage_container,
    storage_path: grant.storage_path,
    original_filename: recording.name,
    size_bytes: recording.size,
    mime_type: recording.type || null,
  };
}

export async function createCandidate(candidate: CandidateSubmissionInput): Promise<Candidate> {
  if (!supabase) throw new Error("Supabase is not configured");

  const candidateFields: CandidateInput = {
    full_name: candidate.full_name,
    external_id: candidate.external_id,
    category: candidate.category,
    verdict: candidate.verdict,
    ...(candidate.notes ? { notes: candidate.notes } : {}),
  };
  const response = await authorizedFetch("/api/candidates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...candidateFields, recording: candidate.recording }),
  });
  return (await response.json()) as Candidate;
}
