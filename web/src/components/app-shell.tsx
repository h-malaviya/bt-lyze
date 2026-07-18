import type { PropsWithChildren, ReactNode } from "react";

import { Logo } from "./logo";
import { useAuth } from "../auth/use-auth";

interface AppShellProps extends PropsWithChildren {
  eyebrow: string;
  title: string;
  action?: ReactNode;
}

export function AppShell({ eyebrow, title, action, children }: AppShellProps) {
  const { user, signOut } = useAuth();
  const displayName = user?.full_name || user?.email?.split("@")[0] || "Account";

  return (
    <div className="min-h-screen bg-fog">
      <header className="border-b border-ink/10 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8">
          <Logo />
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="m-0 text-sm font-semibold text-ink">{displayName}</p>
              <p className="m-0 text-xs capitalize text-ink/50">{user?.role}</p>
            </div>
            <button
              type="button"
              onClick={() => void signOut()}
              className="rounded-xl border border-ink/10 px-3.5 py-2 text-sm font-semibold text-ink transition hover:border-ink/25 hover:bg-fog"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-12">
        <div className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-ember">{eyebrow}</p>
            <h1 className="display-font m-0 text-3xl font-bold tracking-tight text-ink sm:text-4xl">{title}</h1>
          </div>
          {action}
        </div>
        {children}
      </main>
    </div>
  );
}
