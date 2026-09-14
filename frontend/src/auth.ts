// Session flow: GET /auth/me → on 401, POST /auth/refresh → retry /auth/me once; concurrent checks share a request, and logout waits before POST /auth/logout.
export type User = {
    id: string;
    email: string;
    name: string | null;
};

export const API_URL = import.meta.env?.VITE_API_URL ?? "http://localhost:8000";
let userRequest: Promise<User | null> | null = null;
let logoutRequest: Promise<void> | null = null;

async function fetchUser(): Promise<User | null> {
    let response = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
    if (response.status === 401) {
        const refresh = await fetch(`${API_URL}/auth/refresh`, {
            method: "POST",
            credentials: "include",
        });
        if (refresh.status === 401) return null;
        if (!refresh.ok) throw new Error("Unable to refresh your session. Please retry.");
        response = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
    }
    if (response.status === 401) return null;
    if (!response.ok) throw new Error("Unable to load your account. Please retry.");
    return response.json();
}

export function loadUser(): Promise<User | null> {
    // Share the entire check/refresh/retry, including React StrictMode's startup checks.
    if (logoutRequest) return logoutRequest.then(() => null);
    if (!userRequest) {
        userRequest = fetchUser().finally(() => { userRequest = null; });
    }
    return userRequest;
}

export function logout(): Promise<void> {
    if (!logoutRequest) {
        const pendingUser = userRequest;
        logoutRequest = (async () => {
            // Revoke the latest cookie if a rotation is already in progress.
            await pendingUser?.catch(() => undefined);
            const response = await fetch(`${API_URL}/auth/logout`, {
                method: "POST",
                credentials: "include",
            });
            if (!response.ok) throw new Error("Unable to log out. Please try again.");
        })().finally(() => { logoutRequest = null; });
    }
    return logoutRequest;
}

export class SessionExpiredError extends Error {}

/** Send cookies, recover an expired session, and retry the request once after a 401. */
export async function authenticatedFetch(path: string, options: RequestInit = {}): Promise<Response> {
    if (logoutRequest) throw new SessionExpiredError("Please sign in again.");
    const request = { ...options, credentials: "include" as const };
    let response = await fetch(`${API_URL}${path}`, request);
    if (response.status === 401) {
        if (!(await loadUser())) throw new SessionExpiredError("Your session expired. Please sign in again.");
        response = await fetch(`${API_URL}${path}`, request);
    }
    if (response.status === 401) throw new SessionExpiredError("Your session expired. Please sign in again.");
    return response;
}
