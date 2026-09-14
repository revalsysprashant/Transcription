// Audio screen: upload or open a saved job → display its transcript → download the original.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { downloadAudio, downloadTranscript, loadAudioLimits, loadAudioJob, uploadAudio, type SavedJob } from "../audio";
import { SessionExpiredError } from "../auth";

import AudioRecorder from "./AudioRecorder";

type Props = {
    disabled: boolean;
    onBusyChange: (busy: boolean) => void;
    onSessionExpired: () => void;
};

/** Keep upload, saved-job lookup, and download feedback in one authenticated screen. */
export default function AudioWorkspace({ disabled, onBusyChange, onSessionExpired }: Props) {
    const [file, setFile] = useState<File | null>(null);
    const [language, setLanguage] = useState("");
    const [jobId, setJobId] = useState("");
    const [job, setJob] = useState<SavedJob | null>(null);
    const [pending, setPending] = useState("");
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [recording, setRecording] = useState(false);
    const [limits, setLimits] = useState<{ max_size_bytes: number; max_duration_seconds: number } | null>(null);
    useEffect(() => {
        let active = true;
        loadAudioLimits().then((value) => { if (active) setLimits(value); })
            .catch(() => { /* Upload errors still display the server-enforced limits. */ });
        return () => { active = false; };
    }, []);
    const inFlight = useRef(false);

    /** Run one action at a time, keeping logout disabled until the request finishes. */
    async function runAction(message: string, action: () => Promise<void>) {
        if (disabled || inFlight.current) return;
        inFlight.current = true;
        setPending(message);
        setError("");
        setNotice("");
        onBusyChange(true);
        try {
            await action();
        } catch (failure) {
            if (failure instanceof SessionExpiredError) onSessionExpired();
            else setError(failure instanceof Error ? failure.message : "Unable to complete the request.");
        } finally {
            inFlight.current = false;
            setPending("");
            onBusyChange(false);
        }
    }

    /** Submit a recording and keep its saved job ID available for later retrieval. */
    async function handleUpload(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!file) return;
        if (file.size === 0) { setError("Choose a non-empty audio file."); return; }
        if (limits && file.size > limits.max_size_bytes) {
            setError(`Audio must be at most ${limits.max_size_bytes / 1_000_000} MB`);
            return;
        }
        await runAction("Uploading and transcribing your audio…", async () => {
            const saved = await uploadAudio(file, language);
            setJob(saved);
            setJobId(saved.id);
            setNotice("Transcription saved. Keep the job ID to reopen it later.");
        });
    }

    /** Open a persisted job without uploading or transcribing its audio again. */
    async function handleLookup(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const id = jobId.trim();
        if (!id) return;
        await runAction("Loading saved transcription…", async () => {
            setJob(await loadAudioJob(id));
        });
    }

    /** Offer the fetched original as a download and release the temporary browser URL. */
    async function handleDownload(format?: "txt" | "srt" | "vtt") {
        if (!job) return;
        await runAction("Preparing audio download…", async () => {
            const blob = format ? await downloadTranscript(job.id, format) : await downloadAudio(job.id);
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = format ? `transcript-${job.id}.${format}` : job.original_filename.replace(/.*[/\\]/, "") || "audio";
            document.body.appendChild(link);
            link.click();
            link.remove();
            // Allow the browser to start consuming the URL before releasing it.
            window.setTimeout(() => URL.revokeObjectURL(url), 1000);
            setNotice("Download started.");
        });
    }

    const busy = disabled || pending !== "" || recording;
    const buttonStyle = "rounded-lg bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50";
    const inputStyle = "mt-2 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm";
    return (
        <section className="mt-8 border-t border-zinc-200 pt-6" aria-busy={pending !== ""}>
            <h2 className="text-xl font-semibold">Transcribe audio</h2>
            <p className="mt-2 text-sm text-zinc-500">Upload a recording to detect speech, transcribe it, and save the result.</p>
            {limits && <p className="mt-2 text-sm text-zinc-500">Maximum {limits.max_size_bytes / 1_000_000} MB and {limits.max_duration_seconds / 60} minutes.</p>}
            <AudioRecorder disabled={disabled || pending !== ""} limits={limits} onReady={setFile}
                onBusyChange={(value) => { setRecording(value); onBusyChange(value); }} />
            {file && <p className="mt-3 text-sm">Selected: {file.name}</p>}
            <form onSubmit={handleUpload} className="mt-5">
                <fieldset disabled={busy} className="space-y-4 disabled:opacity-60">
                    <div>
                        <label htmlFor="audio-file" className="block text-sm font-medium">Recording</label>
                        <input id="audio-file" type="file" accept="audio/*,.mp4,.webm" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-2 block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-zinc-100 file:px-4 file:py-2" />
                    </div>
                    <div>
                        <label htmlFor="language" className="block text-sm font-medium">Language (optional)</label>
                        <input id="language" value={language} onChange={(event) => setLanguage(event.target.value.toLowerCase())} pattern="[a-z]{2}" maxLength={2} placeholder="e.g. en" className={inputStyle} />
                        <p className="mt-1 text-xs text-zinc-500">Leave blank for automatic language detection.</p>
                    </div>
                    <button type="submit" disabled={!file} className={buttonStyle}>Upload and transcribe</button>
                </fieldset>
            </form>
            <form onSubmit={handleLookup} className="mt-8 border-t border-zinc-100 pt-5">
                <fieldset disabled={busy}>
                    <label htmlFor="job-id" className="block text-sm font-medium">Open a saved job</label>
                    <input id="job-id" value={jobId} onChange={(event) => setJobId(event.target.value)} required placeholder="Paste the saved job ID" className={inputStyle} />
                    <button type="submit" className={`${buttonStyle} mt-3`}>Open job</button>
                </fieldset>
            </form>
            {pending && <p role="status" className="mt-4 text-sm text-zinc-600">{pending}</p>}
            {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            {notice && <p role="status" className="mt-4 text-sm text-green-800">{notice}</p>}
            {job && <section className="mt-8 border-t border-zinc-200 pt-5">
                <h2 className="break-words text-xl font-semibold">{job.original_filename}</h2>
                <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                    <div><dt className="text-zinc-500">Status</dt><dd>{job.status}</dd></div>
                    <div><dt className="text-zinc-500">Size</dt><dd>{job.size_mb.toFixed(2)} MB</dd></div>
                    <div><dt className="text-zinc-500">Duration</dt><dd>{job.duration_seconds?.toFixed(2) ?? "—"} seconds</dd></div>
                    <div><dt className="text-zinc-500">Language</dt><dd>{job.detected_language ?? "Not detected"}</dd></div>
                    <div className="col-span-2"><dt className="text-zinc-500">Job ID</dt><dd className="select-all break-all">{job.id}</dd></div>
                </dl>
                <button type="button" disabled={busy} onClick={() => handleDownload()} className={`${buttonStyle} mt-5`}>Download original audio</button>
                <div className="mt-3 flex gap-2">
                    {(["txt", "srt", "vtt"] as const).map((format) => <button key={format} type="button" disabled={busy} onClick={() => handleDownload(format)} className={buttonStyle}>Export {format.toUpperCase()}</button>)}
                </div>
                <h3 className="mt-6 font-semibold">Transcript</h3>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-7">{job.transcript_text || "No speech was detected in this recording."}</p>
                {!!job.segments?.length && <details className="mt-5">
                    <summary className="cursor-pointer text-sm font-medium">Show timestamps</summary>
                    <ol className="mt-3 space-y-3">
                        {job.segments.map((segment, index) => <li key={index} className="rounded-lg bg-zinc-50 p-3 text-sm">
                            <span className="font-mono text-xs text-zinc-500">{segment.start.toFixed(2)}–{segment.end.toFixed(2)} s</span>
                            <p className="mt-1 whitespace-pre-wrap">{segment.text}</p>
                        </li>)}
                    </ol>
                </details>}
            </section>}
        </section>
    );
}
