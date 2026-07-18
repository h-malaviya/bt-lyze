import { type FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/use-auth";
import { Logo } from "../components/logo";
import { hasSupabaseConfig, supabase } from "../lib/supabase";

export function LoginPage() {
  const { user, loading, error: accountError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to={user.role === "admin" ? "/admin" : "/panel"} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    setError(null);
    setSubmitting(true);
    const result = await supabase.auth.signInWithPassword({ email, password });
    if (result.error) setError(result.error.message);
    setSubmitting(false);
  }

  return (
    <main className="min-h-screen bg-fog lg:grid lg:grid-cols-[1.1fr_0.9fr]">
      <section className="paper-grid relative hidden min-h-screen overflow-hidden bg-moss p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <Logo inverse />
        <div className="relative z-10 max-w-xl pb-12">
          <p className="mb-5 text-xs font-bold uppercase tracking-[0.25em] text-[#9fd4bd]">From conversation to signal</p>
          <h1 className="display-font m-0 text-5xl font-bold leading-[1.08] tracking-[-0.04em] xl:text-6xl">
            Better interviews deserve better evidence.
          </h1>
          <p className="mt-6 max-w-lg text-lg leading-8 text-white/65">
            Record once. Get a searchable transcript, consistent scoring, and a hiring summary your whole team can trust.
          </p>
        </div>
        <div className="absolute -bottom-28 -right-24 h-96 w-96 rounded-full border-[70px] border-white/[0.045]" />
      </section>

      <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-12 lg:hidden"><Logo /></div>
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-ember">Secure workspace</p>
          <h2 className="display-font m-0 text-3xl font-bold tracking-tight text-ink">Welcome back</h2>
          <p className="mb-8 mt-3 text-ink/55">Sign in with the account created for your panel.</p>

          {!hasSupabaseConfig ? (
            <div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-sm leading-6 text-amber-950">
              <p className="m-0 font-bold">One setup step remains</p>
              <p className="mb-0 mt-1">Add the two <code>VITE_SUPABASE_*</code> values to your <code>.env</code>, then rebuild the web container.</p>
            </div>
          ) : (
            <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
              <label className="block text-sm font-semibold text-ink">
                Email address
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-ink/15 bg-white px-4 py-3.5 text-ink outline-none transition placeholder:text-ink/30 focus:border-moss focus:ring-4 focus:ring-mint"
                  placeholder="panel@company.com"
                />
              </label>
              <div>
                <label htmlFor="login-password" className="block text-sm font-semibold text-ink">
                  Password
                </label>
                <div className="relative mt-2">
                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="w-full rounded-xl border border-ink/15 bg-white py-3.5 pl-4 pr-14 text-ink outline-none transition placeholder:text-ink/30 focus:border-moss focus:ring-4 focus:ring-mint"
                    placeholder="At least 8 characters"
                  />
                  <button
                    type="button"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((visible) => !visible)}
                    className="absolute inset-y-0 right-0 grid w-12 place-items-center rounded-r-xl text-ink/45 transition hover:text-moss focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-moss"
                  >
                    {showPassword ? (
                      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8">
                        <path d="M3 3l18 18" strokeLinecap="round" />
                        <path d="M10.6 6.2A10.7 10.7 0 0112 6c6.25 0 9.75 6 9.75 6a17 17 0 01-2.4 3.2M6.2 6.2C3.65 8.1 2.25 12 2.25 12S5.75 18 12 18a10.2 10.2 0 004.1-.85" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M9.9 9.9a3 3 0 004.2 4.2" strokeLinecap="round" />
                      </svg>
                    ) : (
                      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8">
                        <path d="M2.25 12s3.5-6 9.75-6 9.75 6 9.75 6-3.5 6-9.75 6S2.25 12 2.25 12z" strokeLinecap="round" strokeLinejoin="round" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
              {(error || accountError) && (
                <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error || accountError}</p>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-xl bg-moss px-5 py-3.5 font-bold text-white shadow-lg shadow-moss/15 transition hover:bg-[#113d30] disabled:cursor-wait disabled:opacity-60"
              >
                {submitting ? "Signing in…" : "Sign in"}
              </button>
            </form>
          )}
          <p className="mt-8 text-center text-xs leading-5 text-ink/40">Interview data is private and visible only to your panel and administrators.</p>
        </div>
      </section>
    </main>
  );
}
