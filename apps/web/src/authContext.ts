import { createContext, useContext } from "react";

import type { AuthenticatedUser } from "./api";

export type SessionState =
  | { status: "loading" }
  | { status: "authenticated"; user: AuthenticatedUser }
  | { status: "anonymous" }
  | { status: "unavailable" };

export type AuthContextValue = {
  session: SessionState;
  setAuthenticated(user: AuthenticatedUser): void;
};

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
