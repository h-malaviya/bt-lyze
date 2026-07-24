import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

import { searchStudents, type Student } from "../data/students";

interface StudentSelectorProps {
  disabled: boolean;
  externalId: string;
  fullName: string;
  idDisabled: boolean;
  onExternalIdChange: (externalId: string) => void;
  onQueryChange: (query: string) => void;
  onSelect: (student: Student) => void;
}

const CATEGORY_LABELS = {
  ai_ml: "AI/ML Engineer",
  full_stack_engineer: "Software Engineer",
} as const;

export function StudentSelector({
  disabled,
  externalId,
  fullName,
  idDisabled,
  onExternalIdChange,
  onQueryChange,
  onSelect,
}: StudentSelectorProps) {
  const listboxId = useId();
  const helpId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const matches = useMemo(() => searchStudents(fullName), [fullName]);

  useEffect(() => {
    setActiveIndex(0);
  }, [fullName]);

  useEffect(() => {
    if (!open) return;
    function handleOutsidePointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", handleOutsidePointer);
    return () => document.removeEventListener("pointerdown", handleOutsidePointer);
  }, [open]);

  function selectStudent(student: Student) {
    onSelect(student);
    setOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      if (open) event.stopPropagation();
      setOpen(false);
      return;
    }
    if (!open || matches.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % matches.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + matches.length) % matches.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      selectStudent(matches[activeIndex]);
    }
  }

  const hasQuery = Boolean(fullName.trim());
  const activeOptionId = open && matches.length > 0
    ? `${listboxId}-option-${matches[activeIndex].id}`
    : undefined;

  return (
    <div ref={rootRef}>
      <label htmlFor={`${listboxId}-input`} className="block text-sm font-semibold text-ink">
        Student name <span className="text-ember">*</span>
      </label>
      <div className="relative mt-2">
        <div className="pointer-events-none absolute inset-y-0 left-0 grid w-12 place-items-center text-ink/40">
          <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2">
            <circle cx="11" cy="11" r="6" />
            <path d="m16 16 4 4" strokeLinecap="round" />
          </svg>
        </div>
        <input
          id={`${listboxId}-input`}
          autoFocus
          autoComplete="off"
          role="combobox"
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-describedby={helpId}
          aria-expanded={open && hasQuery}
          aria-activedescendant={activeOptionId}
          required
          maxLength={200}
          disabled={disabled}
          value={fullName}
          onChange={(event) => {
            onQueryChange(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Start typing a student name"
          className="w-full rounded-xl border border-ink/15 py-3.5 pl-12 pr-12 text-base outline-none transition placeholder:text-ink/35 focus:border-moss focus:ring-4 focus:ring-mint disabled:bg-fog disabled:text-ink/55"
        />
        {fullName && !disabled && (
          <button
            type="button"
            aria-label="Clear student search"
            onClick={() => {
              onQueryChange("");
              setOpen(false);
            }}
            className="absolute inset-y-0 right-0 grid w-12 place-items-center rounded-r-xl text-xl text-ink/45 transition hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-moss"
          >
            ×
          </button>
        )}

        {open && hasQuery && !disabled && (
          <div
            id={listboxId}
            role="listbox"
            aria-label="Matching students"
            className="absolute inset-x-0 top-full z-20 mt-2 max-h-72 overflow-y-auto overscroll-contain rounded-2xl border border-ink/10 bg-white p-2 shadow-2xl"
          >
            {matches.length > 0 ? matches.map((student, index) => (
              <button
                key={student.id}
                id={`${listboxId}-option-${student.id}`}
                type="button"
                role="option"
                aria-selected={student.id === externalId}
                onClick={() => selectStudent(student)}
                onMouseEnter={() => setActiveIndex(index)}
                className={`flex min-h-16 w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition ${
                  index === activeIndex ? "bg-mint" : "hover:bg-fog"
                }`}
              >
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-bold ${
                  student.id === externalId ? "bg-moss text-white" : "bg-fog text-moss"
                }`}>
                  {student.id === externalId ? "✓" : student.name.charAt(0)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-bold text-ink">{student.name}</span>
                  <span className="mt-0.5 block text-xs text-ink/50">
                    {student.id} · {CATEGORY_LABELS[student.category]}
                  </span>
                </span>
              </button>
            )) : (
              <div className="px-4 py-5 text-center">
                <p className="m-0 text-sm font-bold text-ink">No student found</p>
                <p className="mb-0 mt-1 text-xs leading-5 text-ink/50">Check the spelling or try the enrollment ID.</p>
              </div>
            )}
          </div>
        )}
      </div>
      <p id={helpId} className="mb-0 mt-2 text-xs leading-5 text-ink/50">
        Select a match to prefill the details. You can edit the name and ID afterward.
      </p>

      <label htmlFor={`${listboxId}-student-id`} className="mt-4 block text-sm font-semibold text-ink">
        Student ID <span className="text-ember">*</span>
      </label>
      <input
        id={`${listboxId}-student-id`}
        required
        maxLength={100}
        disabled={idDisabled}
        value={externalId}
        onChange={(event) => onExternalIdChange(event.target.value)}
        placeholder="Enrollment number"
        className="mt-2 w-full rounded-xl border border-ink/15 bg-white px-4 py-3.5 text-base font-semibold text-ink outline-none transition placeholder:font-normal placeholder:text-ink/35 focus:border-moss focus:ring-4 focus:ring-mint disabled:bg-fog disabled:text-ink/55"
      />
    </div>
  );
}
