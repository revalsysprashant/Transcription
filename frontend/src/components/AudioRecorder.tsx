// Recording flow: microphone → audio chunks → previewable File → existing upload form.
import { useEffect, useRef, useState } from "react";

type Props = {
    disabled: boolean;
    limits: { max_size_bytes: number; max_duration_seconds: number } | null;
    onReady: (file: File | null) => void;
    onBusyChange: (busy: boolean) => void;
};

/** Record locally; stopping produces a file for review before the user uploads it. */
export default function AudioRecorder({ disabled, limits, onReady, onBusyChange }: Props) {
    const [active, setActive] = useState(false);
    const [preview, setPreview] = useState("");
    const [error, setError] = useState("");
    const recorder = useRef<MediaRecorder | null>(null);
    const stream = useRef<MediaStream | null>(null);
    const mounted = useRef(false);
    const cancelled = useRef(false);
    const starting = useRef(false);
    const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

    useEffect(() => {
        mounted.current = true;
        return () => {
            mounted.current = false;
            clearTimeout(timer.current);
            if (recorder.current?.state === "recording") recorder.current.stop();
            stream.current?.getTracks().forEach((track) => track.stop());
        };
    }, []);
    useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

    /** Request microphone access, then collect encoded audio until Stop is pressed. */
    async function start() {
        if (disabled || starting.current || active) return;
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
            setError("Recording needs a supported browser on HTTPS or localhost.");
            return;
        }
        cancelled.current = false;
        starting.current = true;
        setActive(true);
        setError("");
        onBusyChange(true);
        try {
            const microphone = await navigator.mediaDevices.getUserMedia({ audio: true });
            if (!mounted.current || cancelled.current) { microphone.getTracks().forEach((track) => track.stop()); return; }
            stream.current = microphone;
            const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"]
                .find((type) => MediaRecorder.isTypeSupported(type));
            const recording = new MediaRecorder(microphone, mimeType ? { mimeType } : undefined);
            recorder.current = recording;
            const chunks: Blob[] = [];
            let bytes = 0;
            let failed = false;
            recording.ondataavailable = (event) => {
                bytes += event.data.size;
                if (limits && bytes > limits.max_size_bytes) {
                    failed = true;
                    if (mounted.current) setError("Recording exceeds the upload size limit. Please record a shorter clip.");
                    if (recording.state === "recording") recording.stop();
                } else if (!failed && event.data.size) chunks.push(event.data);
            };
            recording.onerror = () => {
                failed = true;
                if (mounted.current) setError("Recording failed. Please try again.");
                stop();
            };
            recording.onstop = () => {
                clearTimeout(timer.current);
                microphone.getTracks().forEach((track) => track.stop());
                recorder.current = null;
                if (!mounted.current) return;
                setActive(false);
                onBusyChange(false);
                if (failed) return;
                const type = recording.mimeType || chunks[0]?.type || "audio/webm";
                const blob = new Blob(chunks, { type });
                if (!blob.size) { setError("Recording was empty. Try again."); return; }
                const extension = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
                const file = new File([blob], `recording-${Date.now()}.${extension}`, { type });
                setPreview(URL.createObjectURL(file));
                onReady(file);
            };
            recording.start(1000);
            setPreview("");
            onReady(null);
            if (limits) timer.current = setTimeout(stop, limits.max_duration_seconds * 1000);
        } catch {
            stream.current?.getTracks().forEach((track) => track.stop());
            if (mounted.current) {
                setError("Cannot access the microphone. Check your browser microphone permission.");
                setActive(false);
                onBusyChange(false);
            }
        } finally {
            starting.current = false;
        }
    }

    /** Stop capture; the final data event runs before the preview file is assembled. */
    function stop() {
        cancelled.current = true;
        if (!recorder.current) { setActive(false); onBusyChange(false); }
        if (recorder.current?.state === "recording") recorder.current.stop();
        stream.current?.getTracks().forEach((track) => track.stop());
    }

    return <div className="mt-5 rounded-lg border border-zinc-200 p-4">
        <p className="text-sm font-medium">Record with your microphone</p>
        <div className="mt-3 flex gap-3">
            <button type="button" disabled={disabled || active} onClick={start} className="rounded-lg bg-zinc-950 px-4 py-2 text-sm text-white disabled:opacity-50">Start recording</button>
            <button type="button" disabled={!active} onClick={stop} className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">Stop recording</button>
        </div>
        {active && <p role="status" className="mt-2 text-sm">Microphone active or awaiting permission…</p>}
        {preview && <audio controls src={preview} className="mt-3 w-full" aria-label="Recording preview" />}
        {preview && <p className="mt-2 text-sm">Listen, then choose Upload and transcribe below.</p>}
        {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
    </div>;
}
