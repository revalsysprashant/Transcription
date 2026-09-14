# Current audio flow

Send an authenticated `POST /audio/upload` with multipart field `file`.

1. `AudioService.receive_upload` copies the upload into a named temporary file.
2. `probe_audio` inspects the original metadata.
3. `get_normalized_metadata` creates mono, 16 kHz, 16-bit PCM WAV using FFmpeg.
4. `detect_speech` in `app/repositories/speech.py` runs Silero VAD on that WAV.
5. The response includes original metadata and `normalized` metadata with
   `speech_ranges`, such as `[{"start": 1.2, "end": 4.8}]` (seconds).
6. `extract_speech_clips` copies each range into a separate temporary WAV.
   `normalized.speech_clips` describes each clip's filename, original start/end,
   duration in seconds, and size in MB.
7. After successful transcription, `AudioStorageService` copies the original to
   permanent local storage and commits a `COMPLETED` row in `transcriptions`.
   Temporary normalized files and clips are deleted; the original copy remains.

An empty `speech_ranges` list means no speech was detected. It is a successful
inspection, not a server error. VAD does not identify words, guarantee that every
sound is correctly classified, remove noise, or alter the audio.

## Helper input, processing, output

- Input: a normalized WAV path that still exists.
- Processing: Python's `wave` module reads PCM bytes; NumPy converts them to
  floating-point samples; Silero finds speech boundaries.
- Output: ordered speech ranges in seconds on the original timeline.

The packaged ONNX model is loaded once on CPU. A lock prevents concurrent requests
from interfering with its internal state. Detection runs in the existing worker
thread flow before the normalized file is deleted.

## Dependencies and checks

Run `uv sync` to install the locked dependencies, including CPU-only PyTorch wheels
selected by `pyproject.toml`. FFmpeg and FFprobe must also be installed on the host.
Silero's model files come with the package; uploads do not download model weights.

Run `uv run python -m pytest -q`. VAD tests cover real silence, the normalized input
requirement, and conversion from sample positions to seconds.

Silero API reference: https://github.com/snakers4/silero-vad

The clip files exist only inside `get_normalized_metadata`'s temporary folder.
To inspect one in the debugger, pause after `speech_clips` is assigned and use
`Path(folder) / speech_clips[0].filename` if the list is nonempty. Filenames in the
response are descriptive, not download links; files are already deleted when
the response arrives. Empty speech ranges produce an empty clip list.

## Transcription setup

Set `GROQ_API_KEY` in your local `.env`, then restart the backend/debugger.
`GROQ_TRANSCRIPTION_MODEL` defaults to `whisper-large-v3-turbo`.
Never commit or send your API key in the upload request.

The same multipart endpoint accepts optional `language` (a two-letter lowercase
code such as `en`). Omit it for automatic detection. Each extracted speech clip
is sent to Groq before temporary cleanup. The response adds
`normalized.transcription` with `text`, `detected_languages`, `segments`, and
`processing_time_ms` (the transcription phase only). Segment timestamps are
relative to the original recording, not the individual clip.

No speech returns empty text/segments without contacting Groq. Missing credentials
return 503; provider failures or unusable responses return 502. Clips are processed
sequentially and the request fails if any clip fails; no partial transcript is
returned. Groq account rate limits and file limits still apply. This version does
not split very long speech clips further or retry paid requests automatically.

Provider reference: https://console.groq.com/docs/speech-to-text
An automatic job-history list is a later step.


## Permanent storage

Successful uploads return `id` and `status: "COMPLETED"` alongside their existing
metadata. Use `GET /audio/{id}` with your auth cookies to retrieve a saved job.
Other users receive 404; requests without authentication receive 401.

Original bytes live at `backend/storage/audio/<user-id>/<job-id>.audio` by default.
Set `AUDIO_STORAGE_DIR` to an absolute path to override this. The `.audio` suffix
is a storage convention; bytes are preserved exactly, and the original filename
is stored in the database. Storage is ignored by Git and is not publicly served.

The database stores original metadata, exact byte count, transcript text, JSON
segments, language, transcription-phase processing time, and completion time.
The existing single detected-language column stores `mixed` for multilingual
results. Saved responses expose size in MB. Silence is saved as a completed
inspection with empty transcript/segments. Failed processing creates no record.

`StorageRepository` handles files; `TranscriptionRepository` handles SQLAlchemy;
`AudioStorageService` owns the commit and removes the copied file if persistence
fails. PostgreSQL and the filesystem do not share an atomic transaction, so an
abrupt process crash can leave an orphan file. Back up both the database and audio
storage if you need durable recovery beyond a local disk.

Existing models and migrations are reused; no schema changes were needed. As usual,
new databases need `uv run alembic upgrade head` before serving requests. This task
does not drop tables or migrate existing data.


## Download original audio

Send `GET /audio/{id}/download` with your authentication cookies. In an API client,
use Save Response / Download to save the attachment. Browsers use the original
filename; directory components in submitted names are removed.

The endpoint returns the exact original bytes, not the normalized WAV or speech
clips. It streams the file and supports byte ranges. Only the owner can download
it. Missing files, unknown jobs, and other users' jobs return 404; missing or expired
authentication returns 401. Refresh the session first when necessary.

The endpoint does not delete the saved audio after download. The frontend Download original audio button calls this endpoint.


## Frontend

After signing in, select a recording and optionally enter a two-letter language
code. Upload and transcribe sends the multipart request to `/audio/upload` and
shows the saved transcript, timestamps, duration, size, and job ID.

Use Open a saved job to retrieve a job by ID after a reload. No automatic history
list exists yet. Download original audio fetches the owned original and offers it
as a browser download. All three requests include cookies and recover once from
an expired session. Provider failures are displayed without automatic resubmission.
Logout and other actions are disabled while an audio request is running.

`frontend/src/audio.ts` owns API calls; `components/AudioWorkspace.tsx` owns the
form and result display; `auth.ts` handles authenticated requests and session recovery.
The frontend never stores authentication tokens or sends an API key to the browser.

## Recording, limits, and transcript exports

Browser flow: **Start recording → Stop recording → listen to preview → Upload and transcribe**.
Microphone access requires HTTPS or localhost and browser permission. Recording stays
local until Upload is clicked. Tracks stop after recording or leaving the screen.
Automatic job history is not enabled; keep a job ID to reopen a result manually.

`GET /audio/limits` exposes the configured limits. Defaults are **25 decimal MB**
and **3600 seconds**; change `MAX_AUDIO_SIZE_MB` and
`MAX_AUDIO_DURATION_SECONDS` in `.env` and restart the backend.
The service checks bytes while copying and duration after probing, before VAD or
Groq. It also checks normalized duration. Rejected uploads return HTTP 413 and
are not saved. FastAPI has already parsed/spooled multipart data before these
service checks; a reverse proxy request-body limit is still needed for an ingress
limit in production. Browser recording stops at the duration limit and rejects
recordings that exceed the byte limit.

Authenticated exports use `GET /audio/{job_id}/export/{format}`, where format is
`txt`, `srt`, or `vtt`. The saved owner alone can export. TXT contains full text;
SRT/VTT contain timestamped cues on the original audio timeline. No extra Groq
request is made. The frontend provides all three export buttons beside the
original audio download.

Local verification: `python -m pytest -q` in backend; `npm run build`,
`npm run lint`, and `node --test tests/*.test.mjs` in frontend.
A real Groq smoke test requires setting `GROQ_API_KEY` locally and uploading a
short spoken recording. Silent audio exercises storage and downloads without
contacting the transcription provider.

Verification on 2026-09-14: 55 backend tests and 15 frontend API/auth tests passed;
frontend build and lint passed. Headless Chromium with a synthetic silent microphone
exercised actual browser recording, preview, upload, FFmpeg/Silero processing,
PostgreSQL persistence, original-audio and TXT/SRT/VTT downloads, and reopening a
saved recording after reload. Test data was removed afterward. Google sign-in was
not repeated (the browser used a test user's auth cookie), and Groq was not called
because `GROQ_API_KEY` was unset. Browser WebM files without duration metadata are
supported by measuring audio packet timestamps in the probe helper.
