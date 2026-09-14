// Login screen: renders the Google sign-in button and passes its successful-login callback up to App.
import GoogleLoginButton from "../components/GoogleLoginButton";

export default function Login({ onLogin }: { onLogin: () => Promise<void> }) {
    const features = [
        { number: "01", label: "Upload audio" },
        { number: "02", label: "AI transcription" },
        { number: "03", label: "Export transcript" },
    ];

    const waveform = [42, 72, 38, 90, 58, 100, 64, 82, 44, 74, 52, 92, 62];

    return (
        <main className="min-h-screen bg-white text-zinc-900 lg:grid lg:grid-cols-[0.9fr_1.1fr]">
            {/* Login */}
            <section className="flex items-center justify-center px-6 py-12 sm:px-10 lg:px-16">
                <div className="w-full max-w-md">
                    <div className="mb-12 flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-950 text-2xl text-white shadow-lg">
                        ♪
                    </div>

                    <div className="mb-8">
                        <span className="mb-3 block text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                            AI Transcription
                        </span>

                        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
                            Welcome back
                        </h1>

                        <p className="mt-5 text-sm leading-7 text-zinc-500 sm:text-base">
                            Sign in to upload, record, and transform your audio
                            into accurate transcripts.
                        </p>
                    </div>

                    <GoogleLoginButton onLogin={onLogin} />

                    <div className="my-8 flex items-center gap-4">
                        <div className="h-px flex-1 bg-zinc-200" />

                        <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-400">
                            Secure sign in
                        </span>

                        <div className="h-px flex-1 bg-zinc-200" />
                    </div>

                    <div className="grid gap-3 sm:grid-cols-3">
                        {features.map((feature) => (
                            <div
                                key={feature.number}
                                className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4 transition hover:border-zinc-300 hover:bg-zinc-100"
                            >
                                <span className="text-xs font-semibold text-zinc-400">
                                    {feature.number}
                                </span>

                                <p className="mt-3 text-sm font-semibold text-zinc-700">
                                    {feature.label}
                                </p>
                            </div>
                        ))}
                    </div>

                    <p className="mt-8 text-xs leading-5 text-zinc-400">
                        By continuing, you agree to our Terms of Service and
                        Privacy Policy.
                    </p>
                </div>
            </section>

            {/* Visual */}
            <section className="relative hidden min-h-screen overflow-hidden bg-zinc-950 px-16 py-20 text-white lg:flex lg:items-center">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.12),transparent_30%),radial-gradient(circle_at_85%_70%,rgba(255,255,255,0.07),transparent_30%)]" />

                <div className="relative z-10 w-full max-w-2xl">
                    <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs font-medium tracking-wide text-white/60 backdrop-blur">
                        Speech → Text
                    </span>

                    <h2 className="mt-8 text-6xl font-bold leading-[0.95] tracking-[-0.05em] xl:text-7xl">
                        Turn conversations
                        <br />
                        into clarity.
                    </h2>

                    <div className="my-14 flex h-28 items-center gap-2">
                        {waveform.map((height, index) => (
                            <span
                                key={index}
                                className="w-2 rounded-full bg-white/80"
                                style={{
                                    height: `${height}px`,
                                }}
                            />
                        ))}
                    </div>

                    <div className="grid max-w-xl grid-cols-[auto_1fr] gap-5 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-md">
                        <span className="text-xs font-semibold text-white/40">
                            00:08
                        </span>

                        <p className="text-sm leading-7 text-white/70">
                            Your transcription will appear here with timestamps,
                            language detection, and structured speech segments.
                        </p>
                    </div>
                </div>
            </section>
        </main>
    );
}
