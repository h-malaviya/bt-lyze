import { type PropsWithChildren, useCallback, useEffect, useMemo, useState } from "react";

import { getCurrentUser, type CurrentUser } from "../lib/api";
import { supabase } from "../lib/supabase";
import { AuthContext } from "./auth-context";

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!supabase) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    const { data } = await supabase.auth.getSession();
    if (!data.session) {
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      setUser(await getCurrentUser(data.session.access_token));
    } catch (caught) {
      setUser(null);
      setError(caught instanceof Error ? caught.message : "Could not load your account");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    if (!supabase) return;

    const { data } = supabase.auth.onAuthStateChange(() => {
      void refresh();
    });
    return () => data.subscription.unsubscribe();
  }, [refresh]);

  const signOut = useCallback(async () => {
    await supabase?.auth.signOut();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, error, signOut, refresh }),
    [error, loading, refresh, signOut, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
