// Audio API: upload and retrieve jobs, then fetch original audio with cookie-based authentication.
import { authenticatedFetch } from "./auth";

export type Segment = { start: number; end: number; text: string };
export type SavedJob = {
    id: string;
    original_filename: string;
    size_mb: number;
    duration_seconds: number | null;
    status: string;
    detected_language: string | null;
    transcript_text: string | null;
    segments: Segment[] | null;
    processing_time_ms: number | null;
};

type UploadResult = {
    id: string;
    filename: string | null;
    size_mb: number;
    duration: number;
    status: string;
    normalized: {
        transcription: {
            text: string;
            detected_languages: string[];
            segments: Segment[];
            processing_time_ms: number;
        };
    };
};

/** Turn safe backend error messages into errors the form can display. */
async function checkResponse(response: Response): Promise<void> {
    if (response.ok) return;
    const data = await response.json().catch(() => null);
    const message = typeof data?.detail === "string" ? data.detail : "The request failed. Please try again.";
    throw new Error(message);
}

/** Send the file and optional language; convert the upload result into a saved-job view. */
export async function uploadAudio(file: File, language: string): Promise<SavedJob> {
    const body = new FormData();
    body.append("file", file);
    if (language.trim()) body.append("language", language.trim());
    // The browser sets the multipart Content-Type including its boundary.
    const response = await authenticatedFetch("/audio/upload", { method: "POST", body });
    await checkResponse(response);
    const data: UploadResult = await response.json();
    const transcript = data.normalized.transcription;
    return {
        id: data.id,
        original_filename: data.filename ?? file.name,
        size_mb: data.size_mb,
        duration_seconds: data.duration,
        status: data.status,
        detected_language: transcript.detected_languages.join(", ") || null,
        transcript_text: transcript.text,
        segments: transcript.segments,
        processing_time_ms: transcript.processing_time_ms,
    };
}

/** Retrieve an existing job; the backend verifies ownership using the auth cookie. */
export async function loadAudioJob(id: string): Promise<SavedJob> {
    const response = await authenticatedFetch(`/audio/${encodeURIComponent(id)}`);
    await checkResponse(response);
    return response.json();
}

/** Fetch the original bytes; callers create and release the browser download URL. */
export async function downloadAudio(id: string): Promise<Blob> {
    const response = await authenticatedFetch(`/audio/${encodeURIComponent(id)}/download`);
    await checkResponse(response);
    return response.blob();
}

/** Retrieve server limits; the backend always enforces these again on upload. */
export async function loadAudioLimits(): Promise<{ max_size_bytes: number; max_duration_seconds: number }> {
    const response = await authenticatedFetch("/audio/limits");
    await checkResponse(response);
    return response.json();
}

/** Fetch an owned transcript as UTF-8 text or timed subtitles. */
export async function downloadTranscript(id: string, format: "txt" | "srt" | "vtt"): Promise<Blob> {
    const response = await authenticatedFetch(`/audio/${encodeURIComponent(id)}/export/${format}`);
    await checkResponse(response);
    return response.blob();
}
