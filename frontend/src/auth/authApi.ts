import type { AuthUser } from "./permissions";

export interface AuthSession {
  user: AuthUser;
  csrf_token: string;
  expires_at: number;
}

const configuredBase = (import.meta.env.VITE_AUTH_API_BASE_URL as string | undefined)?.replace(/\/$/, "");
const authBase = configuredBase ?? "/api";
let csrfToken = "";

export function setCsrfToken(value: string) { csrfToken = value; }
export function getCsrfToken() { return csrfToken; }

async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${authBase}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        ...init?.headers,
      },
    });
  } catch (cause) {
    const detail = cause instanceof Error ? cause.message : "Network request failed.";
    throw new Error(`Authentication service unavailable: ${detail}`, { cause });
  }
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Authentication API not found. Start the UrbanLens FastAPI backend or configure VITE_AUTH_API_BASE_URL to point to an auth server.");
    }
    throw new Error(body?.detail ?? `Authentication failed (${response.status}).`);
  }
  return body as T;
}

export const authApi = {
  setupStatus: () => authRequest<{ setup_required: boolean; registration_enabled: boolean }>("/auth/setup/status"),
  createInitialAdministrator: (user: { email: string; name: string; password: string }) =>
    authRequest<AuthUser>("/auth/setup/administrator", { method: "POST", body: JSON.stringify(user) }),
  register: (user: { email: string; name: string; role: Exclude<AuthUser["role"], "administrator">; password: string }) =>
    authRequest<AuthUser>("/auth/register", { method: "POST", body: JSON.stringify(user) }),
  session: () => authRequest<AuthSession>("/auth/session"),
  login: (email: string, password: string) => authRequest<AuthSession>("/auth/login", {
    method: "POST", body: JSON.stringify({ email, password }),
  }),
  logout: () => authRequest<{ logged_out: boolean }>("/auth/logout", { method: "POST", body: "{}" }),
  users: () => authRequest<AuthUser[]>("/auth/users"),
  createUser: (user: { email: string; name: string; role: AuthUser["role"]; password: string }) =>
    authRequest<AuthUser>("/auth/users", { method: "POST", body: JSON.stringify(user) }),
  updateUser: (id: string, update: { role?: AuthUser["role"]; active?: boolean; name?: string }) =>
    authRequest<AuthUser>(`/auth/users/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(update) }),
};
