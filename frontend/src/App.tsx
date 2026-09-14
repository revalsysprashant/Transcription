// Auth flow: loadUser checks the session on startup; Login reports sign-in success; App shows the account and returns to Login after logout.
import { useEffect, useState } from "react";
import Login from "./pages/Login";
import AudioWorkspace from "./components/AudioWorkspace";

import { loadUser, logout, type User } from "./auth";

function App() {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [loggingOut, setLoggingOut] = useState(false);
    const [audioBusy, setAudioBusy] = useState(false);

    useEffect(() => {
        let active = true;
        loadUser()
            .then((account) => { if (active) setUser(account); })
            .catch(() => { if (active) setError("Unable to load your account. Please reload to retry."); })
            .finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, []);

    async function handleLogin() {
        const account = await loadUser();
        if (!account) throw new Error("Your session could not be loaded. Please sign in again.");
        setError("");
        setUser(account);
    }

    async function handleLogout() {
        setLoggingOut(true);
        setError("");
        try {
            await logout();
            setUser(null);
        } catch {
            setError("Unable to log out. Please try again.");
        } finally {
            setLoggingOut(false);
        }
    }

    if (loading) {
        return <main className="flex min-h-screen items-center justify-center bg-white text-zinc-600" role="status">Loading your account…</main>;
    }

    if (!user) {
        return <>
            {error && <p role="alert" className="bg-red-50 px-6 py-3 text-sm text-red-700">{error}</p>}
            <Login onLogin={handleLogin} />
        </>;
    }

    return (
        <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-6 py-10 text-zinc-900">
            <section className="w-full max-w-3xl rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">AI Transcription</p>
                <h1 className="mt-4 text-3xl font-bold">Welcome{user.name ? `, ${user.name}` : ""}</h1>
                <p className="mt-3 text-zinc-600">{user.email}</p>
                {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
                <button type="button" onClick={handleLogout} disabled={loggingOut || audioBusy} className="mt-6 rounded-xl bg-zinc-950 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">
                    {loggingOut ? "Logging out…" : "Log out"}
                </button>
                <AudioWorkspace
                    disabled={loggingOut}
                    onBusyChange={setAudioBusy}
                    onSessionExpired={() => {
                        setUser(null);
                        setError("Your session expired. Please sign in again.");
                    }}
                />
            </section>
        </main>
    );
}

export default App;
