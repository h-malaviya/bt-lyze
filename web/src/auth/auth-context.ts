import { createContext } from "react";

import type { CurrentUser } from "../lib/api";

export interface AuthState {
  user: CurrentUser | null;
  loading: boolean;
  error: string | null;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);
