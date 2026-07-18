import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  CandidateCategory,
  UploadedRecording,
  Verdict,
} from "../lib/api";

export interface CandidateDraft {
  fullName: string;
  externalId: string;
  category: CandidateCategory | "";
  verdict: Verdict;
  notes: string;
  uploadedRecording: UploadedRecording | null;
}

const EMPTY_DRAFT: CandidateDraft = {
  fullName: "",
  externalId: "",
  category: "",
  verdict: "selected",
  notes: "",
  uploadedRecording: null,
};

const CATEGORIES = new Set<CandidateCategory>(["ai_ml", "full_stack_engineer"]);
const VERDICTS = new Set<Verdict>(["selected", "not_decided", "not_selected"]);

function isExpectedStorageError(error: unknown): boolean {
  return error instanceof DOMException || error instanceof SyntaxError;
}

function isUploadedRecording(value: unknown): value is UploadedRecording {
  if (!value || typeof value !== "object") return false;
  const recording = value as Record<string, unknown>;
  return (
    (recording.storage_provider === "azure" || recording.storage_provider === "supabase")
    && typeof recording.storage_container === "string"
    && typeof recording.storage_path === "string"
    && typeof recording.original_filename === "string"
    && typeof recording.size_bytes === "number"
    && (typeof recording.mime_type === "string" || recording.mime_type === null)
  );
}

function loadDraft(storageKey: string): CandidateDraft {
  try {
    const stored = window.sessionStorage.getItem(storageKey);
    if (!stored) return { ...EMPTY_DRAFT };
    const value = JSON.parse(stored) as Record<string, unknown>;
    return {
      fullName: typeof value.fullName === "string" ? value.fullName : "",
      externalId: typeof value.externalId === "string" ? value.externalId : "",
      category: CATEGORIES.has(value.category as CandidateCategory)
        ? value.category as CandidateCategory
        : "",
      verdict: VERDICTS.has(value.verdict as Verdict) ? value.verdict as Verdict : "selected",
      notes: typeof value.notes === "string" ? value.notes : "",
      uploadedRecording: isUploadedRecording(value.uploadedRecording)
        ? value.uploadedRecording
        : null,
    };
  } catch (error) {
    if (isExpectedStorageError(error)) return { ...EMPTY_DRAFT };
    throw error;
  }
}

function isEmptyDraft(draft: CandidateDraft): boolean {
  return (
    !draft.fullName
    && !draft.externalId
    && !draft.category
    && draft.verdict === "selected"
    && !draft.notes
    && !draft.uploadedRecording
  );
}

export function useCandidateDraft(ownerId: string) {
  const storageKey = useMemo(() => `intervue:candidate-draft:${ownerId}`, [ownerId]);
  const [draft, setDraft] = useState<CandidateDraft>(() => loadDraft(storageKey));

  useEffect(() => {
    try {
      if (isEmptyDraft(draft)) {
        window.sessionStorage.removeItem(storageKey);
      } else {
        window.sessionStorage.setItem(storageKey, JSON.stringify(draft));
      }
    } catch (error) {
      if (!isExpectedStorageError(error)) throw error;
    }
  }, [draft, storageKey]);

  const updateDraft = useCallback((update: Partial<CandidateDraft>) => {
    setDraft((current) => ({ ...current, ...update }));
  }, []);

  const clearDraft = useCallback(() => {
    try {
      window.sessionStorage.removeItem(storageKey);
    } catch (error) {
      if (!isExpectedStorageError(error)) throw error;
    }
    setDraft({ ...EMPTY_DRAFT });
  }, [storageKey]);

  return { draft, updateDraft, clearDraft };
}
