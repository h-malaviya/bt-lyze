import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import {
  cleanupRecordingUpload,
  uploadCandidateRecording,
  type CandidateCategory,
  type CandidateSubmissionInput,
  type Verdict,
} from "../lib/api";
import { useCandidateDraft } from "../hooks/use-candidate-draft";

interface AddCandidateDialogProps {
  draftOwnerId: string;
  open: boolean;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (candidate: CandidateSubmissionInput) => Promise<void>;
}

type UploadStatus = "idle" | "uploading" | "completed" | "failed";

function fileSize(sizeBytes: number): string {
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function radioCardClass(selected: boolean): string {
  return [
    "flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3.5 text-sm font-semibold",
    "transition focus-within:ring-4 focus-within:ring-mint",
    selected ? "border-moss bg-mint text-moss" : "border-ink/15 bg-white text-ink/70",
  ].join(" ");
}

export function AddCandidateDialog({
  draftOwnerId,
  open,
  pending,
  error,
  onClose,
  onSubmit,
}: AddCandidateDialogProps) {
  const { draft, updateDraft, clearDraft } = useCandidateDraft(draftOwnerId);
  const { fullName, externalId, category, verdict, notes, uploadedRecording } = draft;
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>(
    uploadedRecording ? "completed" : "idle",
  );
  const [uploadProgress, setUploadProgress] = useState(uploadedRecording ? 100 : 0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(
    uploadedRecording?.original_filename ?? null,
  );
  const uploadController = useRef<AbortController | null>(null);
  const uploadAttempt = useRef(0);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || pending) return;
      uploadAttempt.current += 1;
      uploadController.current?.abort();
      if (uploadedRecording) {
        void cleanupRecordingUpload(uploadedRecording).catch(() => undefined);
      }
      clearDraft();
      setUploadStatus("idle");
      setUploadProgress(0);
      setUploadError(null);
      setSelectedFilename(null);
      onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [clearDraft, onClose, open, pending, uploadedRecording]);

  if (!open) return null;

  function discardAndClose() {
    if (pending) return;
    uploadAttempt.current += 1;
    uploadController.current?.abort();
    if (uploadedRecording) {
      void cleanupRecordingUpload(uploadedRecording).catch(() => undefined);
    }
    clearDraft();
    setUploadStatus("idle");
    setUploadProgress(0);
    setUploadError(null);
    setSelectedFilename(null);
    onClose();
  }

  async function handleRecordingChange(event: ChangeEvent<HTMLInputElement>) {
    const recording = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!recording || !fullName.trim()) return;

    const attempt = uploadAttempt.current + 1;
    uploadAttempt.current = attempt;
    uploadController.current?.abort();
    if (uploadedRecording) {
      try {
        await cleanupRecordingUpload(uploadedRecording);
      } catch {
        if (attempt !== uploadAttempt.current) return;
        setUploadStatus("failed");
        setUploadError("The previous recording could not be removed. Please try again.");
        return;
      }
    }

    const controller = new AbortController();
    uploadController.current = controller;
    updateDraft({ uploadedRecording: null });
    setSelectedFilename(recording.name);
    setUploadStatus("uploading");
    setUploadProgress(0);
    setUploadError(null);
    try {
      const uploaded = await uploadCandidateRecording(
        fullName.trim(),
        recording,
        (percentage) => {
          if (attempt === uploadAttempt.current) setUploadProgress(percentage);
        },
        controller.signal,
      );
      if (attempt !== uploadAttempt.current) {
        void cleanupRecordingUpload(uploaded).catch(() => undefined);
        return;
      }
      updateDraft({ uploadedRecording: uploaded });
      setUploadProgress(100);
      setUploadStatus("completed");
    } catch (uploadFailure) {
      if (attempt !== uploadAttempt.current) return;
      if (uploadFailure instanceof DOMException && uploadFailure.name === "AbortError") {
        setUploadStatus("idle");
        return;
      }
      setUploadStatus("failed");
      setUploadError(
        uploadFailure instanceof Error ? uploadFailure.message : "Recording upload failed",
      );
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!uploadedRecording || !externalId.trim() || !category) return;
    try {
      await onSubmit({
        full_name: fullName,
        external_id: externalId.trim(),
        category,
        verdict,
        recording: uploadedRecording,
        ...(notes.trim() ? { notes: notes.trim() } : {}),
      });
    } catch {
      return;
    }
    clearDraft();
    setUploadStatus("idle");
    setUploadProgress(0);
    setSelectedFilename(null);
    onClose();
  }

  const nameLocked = pending || uploadStatus === "uploading" || uploadStatus === "completed";
  const canSubmit = Boolean(
    fullName.trim()
      && externalId.trim()
      && category
      && uploadStatus === "completed"
      && uploadedRecording,
  );

  return (
    <div className="fixed inset-0 z-50 grid place-items-end bg-ink/40 p-0 backdrop-blur-sm sm:place-items-center sm:p-5">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-candidate-title"
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-white p-6 shadow-2xl sm:max-w-xl sm:rounded-3xl sm:p-8"
      >
        <div className="mb-7 flex items-start justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-ember">New interview</p>
            <h2 id="add-candidate-title" className="display-font m-0 text-2xl font-bold text-ink">Add candidate</h2>
          </div>
          <button type="button" onClick={discardAndClose} disabled={pending} aria-label="Close" className="grid h-10 w-10 place-items-center rounded-xl border border-ink/10 text-xl text-ink/55 transition hover:bg-fog disabled:opacity-40">×</button>
        </div>

        <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
          <label className="block text-sm font-semibold text-ink">
            Candidate name <span className="text-ember">*</span>
            <input autoFocus required maxLength={200} disabled={nameLocked} value={fullName} onChange={(event) => updateDraft({ fullName: event.target.value })} placeholder="Full name" className="mt-2 w-full rounded-xl border border-ink/15 px-4 py-3.5 outline-none transition focus:border-moss focus:ring-4 focus:ring-mint disabled:bg-fog disabled:text-ink/55" />
          </label>

          <label className="block text-sm font-semibold text-ink">
            Candidate ID <span className="text-ember">*</span>
            <input required maxLength={100} disabled={pending} value={externalId} onChange={(event) => updateDraft({ externalId: event.target.value })} placeholder="Enrollment number" className="mt-2 w-full rounded-xl border border-ink/15 px-4 py-3.5 outline-none transition focus:border-moss focus:ring-4 focus:ring-mint disabled:bg-fog" />
          </label>

          <fieldset disabled={pending} className="m-0 border-0 p-0">
            <legend className="text-sm font-semibold text-ink">
              Category <span className="text-ember">*</span>
            </legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {([
                ["ai_ml", "AI/ML"],
                ["full_stack_engineer", "Full Stack Engineer"],
              ] as const).map(([value, label]) => (
                <label key={value} className={radioCardClass(category === value)}>
                  <input
                    type="radio"
                    name="candidate-category"
                    value={value}
                    required
                    checked={category === value}
                    onChange={() => updateDraft({ category: value as CandidateCategory })}
                    className="h-4 w-4 accent-moss"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset disabled={pending} className="m-0 border-0 p-0">
            <legend className="text-sm font-semibold text-ink">Panel verdict</legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-3">
              {([
                ["selected", "Selected"],
                ["not_decided", "Not decided"],
                ["not_selected", "Not selected"],
              ] as const).map(([value, label]) => (
                <label key={value} className={radioCardClass(verdict === value)}>
                  <input
                    type="radio"
                    name="panel-verdict"
                    value={value}
                    checked={verdict === value}
                    onChange={() => updateDraft({ verdict: value as Verdict })}
                    className="h-4 w-4 accent-moss"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <label className="block text-sm font-semibold text-ink">
            Interview notes
            <textarea rows={4} maxLength={5000} disabled={pending} value={notes} onChange={(event) => updateDraft({ notes: event.target.value })} placeholder="Optional context for the hiring team" className="mt-2 w-full resize-y rounded-xl border border-ink/15 px-4 py-3.5 outline-none transition focus:border-moss focus:ring-4 focus:ring-mint disabled:bg-fog" />
          </label>

          <label className="block text-sm font-semibold text-ink">
            Interview recording <span className="text-ember">*</span>
            <input type="file" accept="audio/*,video/*" disabled={pending || uploadStatus === "uploading" || !fullName.trim()} onChange={(event) => void handleRecordingChange(event)} className="mt-2 block w-full rounded-xl border border-dashed border-ink/20 bg-fog px-4 py-5 text-sm text-ink/65 file:mr-4 file:rounded-lg file:border-0 file:bg-mint file:px-4 file:py-2 file:font-bold file:text-moss disabled:opacity-50" />
            <span className="mt-2 block text-xs font-normal text-ink/45">
              {fullName.trim() ? "Selecting a file starts the upload immediately." : "Enter the candidate name before selecting a recording."}
            </span>
          </label>

          {uploadStatus !== "idle" && (
            <section aria-live="polite" className="rounded-xl border border-ink/10 bg-fog p-4">
              <div className="flex items-center justify-between gap-4 text-sm">
                <span className="min-w-0 truncate font-semibold text-ink">{selectedFilename}</span>
                <span className={uploadStatus === "completed" ? "font-bold text-moss" : "font-bold text-ink/55"}>
                  {uploadStatus === "completed" ? "Uploaded" : uploadStatus === "failed" ? "Failed" : `${uploadProgress}%`}
                </span>
              </div>
              <div role="progressbar" aria-label="Recording upload progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress} className="mt-3 h-2 overflow-hidden rounded-full bg-ink/10">
                <div className={`h-full rounded-full transition-[width] duration-200 ${uploadStatus === "failed" ? "bg-red-500" : "bg-moss"}`} style={{ width: `${uploadProgress}%` }} />
              </div>
              {uploadedRecording && <p className="mb-0 mt-2 text-xs text-ink/45">{fileSize(uploadedRecording.size_bytes)} · ready to submit</p>}
            </section>
          )}

          {(uploadError || error) && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{uploadError ?? error}</p>}

          <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={discardAndClose} disabled={pending} className="rounded-xl border border-ink/15 px-5 py-3 font-bold text-ink hover:bg-fog disabled:opacity-40">Cancel</button>
            <button type="submit" disabled={pending || !canSubmit} className="rounded-xl bg-moss px-6 py-3 font-bold text-white shadow-lg shadow-moss/15 transition hover:bg-[#113d30] disabled:cursor-not-allowed disabled:opacity-50">
              {pending ? "Saving and queuing…" : uploadStatus === "uploading" ? "Uploading recording…" : "Create candidate and queue"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
