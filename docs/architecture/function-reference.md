# Function-by-function reference

This index covers all **85 named functions** in `frontend/src`, `backend/app`, and `backend/alembic`, including React components and nested named handlers. Backend explanations are drawn from implementation docstrings; frontend explanations are maintained in `frontend-explanations.json`. Tests are not application runtime functions.

Anonymous lifecycle and event callbacks, declarative schemas, and deployment scripts are explained in [the architecture guide](README.md). The call lists below are syntactic calls found in each function body, not a runtime trace; callbacks and branches may execute only conditionally.

## backend/alembic/env.py

[Open source](../../backend/alembic/env.py)

### `run_migrations_offline`

[Source line 27](../../backend/alembic/env.py#L27)

```python
def run_migrations_offline() -> None
```

Emit migration SQL using the configured URL without opening a DB connection.

**Calls appearing in the body:** `config.get_main_option`, `context.begin_transaction`, `context.configure`, `context.run_migrations`.

### `do_run_migrations`

[Source line 44](../../backend/alembic/env.py#L44)

```python
def do_run_migrations(connection) -> None
```

Apply migrations using the supplied synchronous connection.

Configure model metadata and type comparisons inside an Alembic
transaction; the async runner invokes this through run_sync.

**Calls appearing in the body:** `context.begin_transaction`, `context.configure`, `context.run_migrations`.

### `run_migrations_online`

[Source line 60](../../backend/alembic/env.py#L60)

```python
async def run_migrations_online() -> None
```

Open an async database connection, apply migrations, then dispose the engine.

**Calls appearing in the body:** `async_engine_from_config`, `config.get_section`, `connectable.connect`, `connectable.dispose`, `connection.run_sync`.

## backend/alembic/versions/a2549975a23a_create_users_and_transcriptions.py

[Open source](../../backend/alembic/versions/a2549975a23a_create_users_and_transcriptions.py)

### `upgrade`

[Source line 22](../../backend/alembic/versions/a2549975a23a_create_users_and_transcriptions.py#L22)

```python
def upgrade() -> None
```

Create user and transcription tables, constraints, and indexes.

**Calls appearing in the body:** `op.create_index`, `op.create_table`, `op.f`, `postgresql.JSONB`, `sa.BigInteger`, `sa.Column`, `sa.DateTime`, `sa.Enum`, `sa.Float`, `sa.ForeignKeyConstraint`, `sa.Integer`, `sa.PrimaryKeyConstraint`, `sa.String`, `sa.Text`, `sa.UUID`, `sa.text`.

### `downgrade`

[Source line 62](../../backend/alembic/versions/a2549975a23a_create_users_and_transcriptions.py#L62)

```python
def downgrade() -> None
```

Drop transcription and user tables in dependency order, deleting their data.

**Calls appearing in the body:** `op.drop_index`, `op.drop_table`, `op.f`.

## backend/alembic/versions/adea30e5b1a7_add_refresh_sessions.py

[Open source](../../backend/alembic/versions/adea30e5b1a7_add_refresh_sessions.py)

### `upgrade`

[Source line 22](../../backend/alembic/versions/adea30e5b1a7_add_refresh_sessions.py#L22)

```python
def upgrade() -> None
```

Create refresh-session storage with a user foreign key and unique token hashes.

**Calls appearing in the body:** `op.create_index`, `op.create_table`, `op.f`, `sa.Column`, `sa.DateTime`, `sa.ForeignKeyConstraint`, `sa.PrimaryKeyConstraint`, `sa.String`, `sa.UUID`, `sa.text`.

### `downgrade`

[Source line 40](../../backend/alembic/versions/adea30e5b1a7_add_refresh_sessions.py#L40)

```python
def downgrade() -> None
```

Drop refresh-session indexes and the table, deleting stored sessions.

**Calls appearing in the body:** `op.drop_index`, `op.drop_table`, `op.f`.

## backend/app/core/config.py

[Open source](../../backend/app/core/config.py)

### `get_settings`

[Source line 45](../../backend/app/core/config.py#L45)

```python
def get_settings() -> Settings
```

Return cached, validated application settings loaded from the environment.

Settings also reads .env; missing required values raise validation errors.

**Calls appearing in the body:** `Settings`.

## backend/app/core/database.py

[Open source](../../backend/app/core/database.py)

### `get_db`

[Source line 31](../../backend/app/core/database.py#L31)

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]
```

Yield an AsyncSession for one request and close it afterward.

Roll back pending changes if request handling raises an exception.
Successful requests are not committed automatically; callers own commits.

**Calls appearing in the body:** `AsyncSessionLocal`, `db.rollback`.

## backend/app/core/dependencies.py

[Open source](../../backend/app/core/dependencies.py)

### `get_current_user`

[Source line 10](../../backend/app/core/dependencies.py#L10)

```python
async def get_current_user(access_token: str | None=Cookie(default=None), db: AsyncSession=Depends(get_db)) -> User
```

Resolve the access-token cookie to an authenticated database User.

FastAPI supplies the cookie and request-scoped db session. Missing cookies
or service validation failures become HTTP 401 responses.

**Calls appearing in the body:** `AuthService.get_current_user`, `Cookie`, `Depends`, `HTTPException`, `str`.

## backend/app/core/utils/models.py

[Open source](../../backend/app/core/utils/models.py)

### `load_silero_model`

[Source line 9](../../backend/app/core/utils/models.py#L9)

```python
def load_silero_model()
```

Load and reuse the packaged CPU ONNX model.

Input: none; weights are included in the installed Silero package.
Output: a stateful model. The speech repository holds its lock during use.

**Calls appearing in the body:** `load_silero_vad`, `lru_cache`.

### `create_groq_client`

[Source line 18](../../backend/app/core/utils/models.py#L18)

```python
def create_groq_client(api_key: str) -> AsyncGroq
```

Create an async client for Groq's hosted transcription model.

Input: the configured API key, already checked by the provider.
Output: a new client with a timeout and automatic retries disabled.
The provider closes it using async with. No model weights are loaded locally.

**Calls appearing in the body:** `AsyncGroq`.

## backend/app/core/utils/tokens.py

[Open source](../../backend/app/core/utils/tokens.py)

### `generate_refresh_token`

[Source line 9](../../backend/app/core/utils/tokens.py#L9)

```python
def generate_refresh_token() -> str
```

Return a cryptographically random opaque token for a refresh cookie.

Persist only its hash; the raw value is the browser session credential.

**Calls appearing in the body:** `secrets.token_urlsafe`.

### `hash_refresh_token`

[Source line 17](../../backend/app/core/utils/tokens.py#L17)

```python
def hash_refresh_token(token: str) -> str
```

Return the hexadecimal SHA-256 digest of a raw refresh token.

Use the same digest to store new sessions and look up incoming cookies.

**Calls appearing in the body:** `hashlib.sha256`, `hashlib.sha256(token.encode('utf-8')).hexdigest`, `token.encode`.

### `get_refresh_token_expiry`

[Source line 25](../../backend/app/core/utils/tokens.py#L25)

```python
def get_refresh_token_expiry() -> datetime
```

Return a timezone-aware UTC expiry using the configured refresh lifetime.

**Calls appearing in the body:** `datetime.now`, `timedelta`.

## backend/app/main.py

[Open source](../../backend/app/main.py)

### `lifespan`

[Source line 14](../../backend/app/main.py#L14)

```python
async def lifespan(app: FastAPI)
```

Manage application lifetime and dispose the database engine on shutdown.

The app argument is supplied by FastAPI; startup currently needs no work.

**Calls appearing in the body:** `engine.dispose`.

### `health`

[Source line 46](../../backend/app/main.py#L46)

```python
async def health()
```

Return a basic process-health response.

This endpoint does not check database or external-provider availability.

**Calls appearing in the body:** `app.get`.

## backend/app/providers/groq.py

[Open source](../../backend/app/providers/groq.py)

### `GroqProvider.transcribe`

[Source line 24](../../backend/app/providers/groq.py#L24)

```python
async def transcribe(file_path: Path, language: str | None=None) -> ClipTranscription
```

Send one WAV clip and return its words, language, and segment timestamps.

Input: a temporary clip path and optional language code, such as en.
Processing: request verbose JSON from Groq and validate its fields.
Output: ClipTranscription; timestamps start at zero for this clip.

Omit language for automatic detection. API errors are replaced with safe
messages. The client and file handle are closed even if the request fails.

**Calls appearing in the body:** `ClipTranscription.model_validate`, `TranscriptionProviderError`, `TranscriptionUnavailableError`, `client.audio.transcriptions.create`, `create_groq_client`, `file_path.open`, `response.model_dump`, `settings.groq_api_key.get_secret_value`.

## backend/app/repositories/audio.py

[Open source](../../backend/app/repositories/audio.py)

### `probe_audio`

[Source line 9](../../backend/app/repositories/audio.py#L9)

```python
def probe_audio(file_path: str | Path) -> AudioMetadata
```

Inspect the first audio track without modifying the file.

Input:
    The path of an existing temporary audio file.
Processing:
    Run FFprobe, parse its JSON, and check the first audio track's metadata.
Output:
    An AudioMetadata object with duration, bitrate, sample_rate, channels,
    codec, and format. Bitrate is None when the audio stream omits it.

Raise ValueError for unreadable audio, missing metadata, or a probe timeout.
Raise RuntimeError if FFprobe is unavailable. Browser recordings may omit
duration metadata; measure packet timestamps in that case.

This is a synchronous helper. An async service should call it through
run_in_threadpool so waiting for FFprobe does not block other requests.

**Calls appearing in the body:** `AudioMetadata`, `Path`, `Path(file_path).resolve`, `RuntimeError`, `ValueError`, `audio.get`, `container.get`, `isinstance`, `json.loads`, `measure_packet_duration`, `metadata.get`, `str`, `subprocess.run`.

### `normalize_audio`

[Source line 93](../../backend/app/repositories/audio.py#L93)

```python
def normalize_audio(input_path: str | Path, output_path: str | Path) -> Path
```

Convert audio to mono, 16 kHz, signed 16-bit PCM WAV.

Input: an existing audio file path and a new output path in a temporary folder.
Processing: FFmpeg decodes the first audio track, mixes to mono, and resamples.
Output: the path of the normalized WAV; the original file is not modified.

This does not remove noise, trim silence, or adjust loudness. Run this
synchronous helper in a worker thread. The caller owns temporary-file cleanup,
including any partial output when conversion fails.

**Calls appearing in the body:** `Path`, `Path(input_path).resolve`, `Path(output_path).resolve`, `RuntimeError`, `ValueError`, `destination.exists`, `str`, `subprocess.run`.

### `measure_packet_duration`

[Source line 145](../../backend/app/repositories/audio.py#L145)

```python
def measure_packet_duration(file_path: str | Path) -> float
```

Input browser recording → scan audio packet times → duration in seconds.

MediaRecorder WebM files often omit the container duration. FFprobe can still
read each packet's timestamp and length without decoding the entire audio.

**Calls appearing in the body:** `Path`, `Path(file_path).resolve`, `RuntimeError`, `ValueError`, `float`, `len`, `line.split`, `max`, `min`, `result.stdout.splitlines`, `str`, `subprocess.run`.

## backend/app/repositories/refresh_session.py

[Open source](../../backend/app/repositories/refresh_session.py)

### `RefreshSessionRepository.create`

[Source line 12](../../backend/app/repositories/refresh_session.py#L12)

```python
async def create(db: AsyncSession, *, user_id, token_hash: str, expires_at: datetime) -> RefreshSession
```

Stage a refresh session for user_id using a token hash and UTC expiry.

Flush the insert and return the ORM object without committing. The
caller must commit or roll back, allowing rotation to remain atomic.

**Calls appearing in the body:** `RefreshSession`, `db.add`, `db.flush`.

### `RefreshSessionRepository.revoke`

[Source line 37](../../backend/app/repositories/refresh_session.py#L37)

```python
async def revoke(db: AsyncSession, token_hash: str, *, active_only: bool=False) -> RefreshSession | None
```

Conditionally revoke a session matching token_hash and return it.

Only rows with no revocation time can be updated. With active_only=True,
also require an expiry in the future. Return None when no row qualifies.
The conditional UPDATE prevents double consumption during rotation.
This method never commits; the caller owns the transaction.

**Calls appearing in the body:** `RefreshSession.revoked_at.is_`, `datetime.now`, `db.execute`, `result.scalar_one_or_none`, `statement.values`, `statement.values(revoked_at=now).returning`, `statement.where`, `update`, `update(RefreshSession).where`.

## backend/app/repositories/speech.py

[Open source](../../backend/app/repositories/speech.py)

### `detect_speech`

[Source line 18](../../backend/app/repositories/speech.py#L18)

```python
def detect_speech(file_path: str | Path) -> list[SpeechRange]
```

Find speech in a normalized file without changing or cutting the audio.

Input: mono, 16 kHz, 16-bit PCM WAV created by our normalization helper.
Processing: read PCM samples, scale to floats, and run Silero's speech detector.
Output: ordered start/end ranges in seconds, or [] when no speech is detected.

Run in a worker thread. The model is bundled with silero-vad; requests do not
download weights. Speech detection does not transcribe words or remove noise.

**Calls appearing in the body:** `SpeechRange`, `ValueError`, `audio.getframerate`, `audio.getnchannels`, `audio.getnframes`, `audio.getsampwidth`, `audio.readframes`, `get_speech_timestamps`, `load_silero_model`, `np.frombuffer`, `np.frombuffer(raw_samples, dtype='<i2').astype`, `str`, `torch.from_numpy`, `wave.open`.

### `extract_speech_clips`

[Source line 60](../../backend/app/repositories/speech.py#L60)

```python
def extract_speech_clips(file_path: str | Path, speech_ranges: list[SpeechRange], output_folder: str | Path) -> list[SpeechClip]
```

Copy detected speech intervals into individual temporary PCM WAV files.

Input: normalized WAV, ordered VAD ranges in seconds, and a temporary folder.
Processing: convert times to sample positions and copy only those samples.
Output: clip filenames, original start/end times, duration, and size in MB.

No transcription or re-encoding occurs. Run this helper in a worker thread.
The caller owns the output folder and deletes it after using the clips.
Filenames are relative to that folder, not downloadable URLs.

**Calls appearing in the body:** `Path`, `SpeechClip`, `ValueError`, `clips.append`, `destination.open`, `destination.stat`, `enumerate`, `len`, `math.isfinite`, `min`, `output.setframerate`, `output.setnchannels`, `output.setsampwidth`, `output.writeframesraw`, `round`, `source.getframerate`, `source.getnchannels`, `source.getnframes`, `source.getsampwidth`, `source.readframes`, `source.setpos`, `str`, `wave.open`.

## backend/app/repositories/storage.py

[Open source](../../backend/app/repositories/storage.py)

### `StorageRepository.save_original`

[Source line 13](../../backend/app/repositories/storage.py#L13)

```python
def save_original(source: str | Path, user_id: UUID, job_id: UUID) -> str
```

Copy an original into permanent storage and return a relative storage key.

Input: an existing temporary file and server-controlled user/job UUIDs.
Processing: create a unique file and copy its bytes in bounded chunks.
Output: relative key for the database. Partial files are removed on error.

**Calls appearing in the body:** `Path`, `Path(source).open`, `destination.open`, `destination.parent.mkdir`, `destination.unlink`, `shutil.copyfileobj`.

### `StorageRepository.remove_original`

[Source line 36](../../backend/app/repositories/storage.py#L36)

```python
def remove_original(storage_key: str) -> None
```

Remove a file created by save_original when database persistence fails.

The service supplies the generated key; never pass a client-supplied path.

**Calls appearing in the body:** `(settings.audio_storage_dir / storage_key).unlink`.

### `StorageRepository.get_original_path`

[Source line 44](../../backend/app/repositories/storage.py#L44)

```python
def get_original_path(storage_key: str) -> Path | None
```

Resolve a stored key to an existing file inside the configured storage root.

Input: the key from an owned database record, not a request path.
Output: a local file path, or None if missing or outside storage.
Resolving the path also prevents symlinks from escaping the storage root.

**Calls appearing in the body:** `(root / storage_key).resolve`, `destination.is_file`, `destination.is_relative_to`, `settings.audio_storage_dir.resolve`.

## backend/app/repositories/tokens.py

[Open source](../../backend/app/repositories/tokens.py)

### `create_access_token`

[Source line 10](../../backend/app/repositories/tokens.py#L10)

```python
def create_access_token(user_id: uuid.UUID) -> str
```

Return a signed access JWT for the supplied user UUID.

Include the access token type, issued-at time, and configured expiry.
This function neither persists the token nor sets browser cookies.

**Calls appearing in the body:** `datetime.now`, `jwt.encode`, `str`, `timedelta`.

### `decode_access_token`

[Source line 32](../../backend/app/repositories/tokens.py#L32)

```python
def decode_access_token(token: str) -> dict
```

Verify a JWT signature and claims, then return its decoded payload.

Reject an expired exp claim when present and require type to be access.
Raise ValueError for JWT validation failures or an incorrect token type;
AuthService separately validates the subject UUID and user existence.

**Calls appearing in the body:** `ValueError`, `jwt.decode`, `payload.get`.

## backend/app/repositories/transcription.py

[Open source](../../backend/app/repositories/transcription.py)

### `TranscriptionRepository.create_completed`

[Source line 16](../../backend/app/repositories/transcription.py#L16)

```python
async def create_completed(db: AsyncSession, *, job_id: UUID, user_id: UUID, storage_key: str, result: ReceivedAudio, size_bytes: int, language: str | None) -> Transcription
```

Stage a completed transcription using exact byte counts and JSON segments.

Input: generated IDs, saved file key, and successful processing results.
Output: flushed ORM record; the service must commit or roll back.
The existing single language column uses 'mixed' for multilingual results.

**Calls appearing in the body:** `Transcription`, `datetime.now`, `db.add`, `db.flush`, `len`, `segment.model_dump`.

### `TranscriptionRepository.get_owned`

[Source line 58](../../backend/app/repositories/transcription.py#L58)

```python
async def get_owned(db: AsyncSession, job_id: UUID, user_id: UUID) -> Transcription | None
```

Return a saved job only when it belongs to user_id; otherwise return None.

**Calls appearing in the body:** `db.execute`, `result.scalar_one_or_none`, `select`, `select(Transcription).where`.

## backend/app/repositories/user.py

[Open source](../../backend/app/repositories/user.py)

### `UserRepository.get_by_google_id`

[Source line 12](../../backend/app/repositories/user.py#L12)

```python
async def get_by_google_id(db: AsyncSession, google_id: str) -> User | None
```

Return the user matching Google’s stable subject ID, or None.

Execute a read using db without committing the transaction.

**Calls appearing in the body:** `db.execute`, `result.scalar_one_or_none`, `select`, `select(User).where`.

### `UserRepository.get_by_id`

[Source line 29](../../backend/app/repositories/user.py#L29)

```python
async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None
```

Return the user matching the local UUID, or None, without committing.

**Calls appearing in the body:** `db.execute`, `result.scalar_one_or_none`, `select`, `select(User).where`.

### `UserRepository.create`

[Source line 43](../../backend/app/repositories/user.py#L43)

```python
async def create(db: AsyncSession, *, google_id: str, email: str, name: str | None, avatar_url: str | None) -> User
```

Insert a Google-authenticated user and return the refreshed ORM object.

Unlike refresh-session inserts, this method currently commits db itself.
Optional name and avatar fields may be None.

**Calls appearing in the body:** `User`, `db.add`, `db.commit`, `db.refresh`.

## backend/app/routes/audio.py

[Open source](../../backend/app/routes/audio.py)

### `get_audio_limits`

[Source line 24](../../backend/app/routes/audio.py#L24)

```python
async def get_audio_limits() -> dict[str, int]
```

Return configured upload limits so the browser can show the same rules.

**Calls appearing in the body:** `router.get`.

### `receive_audio`

[Source line 33](../../backend/app/routes/audio.py#L33)

```python
async def receive_audio(file: Annotated[UploadFile, File()], current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], language: Annotated[str | None, Form(pattern='^[a-z]{2}$')]=None) -> SavedAudio
```

Receive the multipart field named file and return its metadata with HTTP 200.

Input: a multipart file, authentication cookie, and optional language code.
Processing: authenticate, normalize, detect speech, and transcribe extracted clips.
Output: saved job ID/status plus audio metadata, transcript text, and timestamps.

FastAPI may temporarily spool the upload to disk while parsing the request.
Closing UploadFile releases that temporary resource. The service separately
preserves the original file and successful transcription in permanent storage.

**Calls appearing in the body:** `AudioService.receive_upload`, `Depends`, `File`, `Form`, `HTTPException`, `file.close`, `router.post`, `str`.

### `get_saved_audio`

[Source line 74](../../backend/app/routes/audio.py#L74)

```python
async def get_saved_audio(job_id: UUID, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> SavedTranscription
```

Retrieve a completed job by ID, restricted to the authenticated owner.

**Calls appearing in the body:** `AudioStorageService.get_saved`, `Depends`, `HTTPException`, `router.get`.

### `download_audio`

[Source line 87](../../backend/app/routes/audio.py#L87)

```python
async def download_audio(job_id: UUID, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> FileResponse
```

Download an owned original recording as an attachment.

Input: saved job ID and authentication cookie.
Output: original audio bytes with the original filename, or HTTP 404.
FileResponse streams the file and supports byte-range requests.

**Calls appearing in the body:** `AudioStorageService.get_download`, `Depends`, `FileResponse`, `HTTPException`, `router.get`.

### `export_transcript`

[Source line 114](../../backend/app/routes/audio.py#L114)

```python
async def export_transcript(job_id: UUID, format: Literal['txt', 'srt', 'vtt'], current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> Response
```

Input owned job ID and format → format saved text → download UTF-8 text.

**Calls appearing in the body:** `AudioStorageService.get_saved`, `Depends`, `HTTPException`, `Response`, `render_transcript`, `router.get`.

## backend/app/routes/auth.py

[Open source](../../backend/app/routes/auth.py)

### `google_login`

[Source line 21](../../backend/app/routes/auth.py#L21)

```python
async def google_login(payload: GoogleLoginRequest, response: Response, db: AsyncSession=Depends(get_db))
```

Exchange a Google credential for authentication cookies.

Delegate login to AuthService and translate ValueError into a sanitized
HTTP 401. Return the service success message through AuthResponse.

**Calls appearing in the body:** `AuthService.login_with_google`, `Depends`, `HTTPException`, `router.post`.

### `get_me`

[Source line 45](../../backend/app/routes/auth.py#L45)

```python
async def get_me(current_user: User=Depends(get_current_user))
```

Return public profile fields for the user resolved by the auth dependency.

Authentication failures are handled before this route body executes.

**Calls appearing in the body:** `Depends`, `router.get`.

### `refresh`

[Source line 61](../../backend/app/routes/auth.py#L61)

```python
async def refresh(response: Response, refresh_token: str | None=Cookie(default=None), db: AsyncSession=Depends(get_db))
```

Pass the refresh cookie to AuthService to rotate the session.

No request body or valid access cookie is required. The service sets
replacement cookies or raises HTTP 401 for invalid refresh credentials.

**Calls appearing in the body:** `AuthService.refresh_tokens`, `Cookie`, `Depends`, `router.post`.

### `logout`

[Source line 75](../../backend/app/routes/auth.py#L75)

```python
async def logout(response: Response, refresh_token: str | None=Cookie(default=None), db: AsyncSession=Depends(get_db))
```

Delegate session revocation and cookie clearing to AuthService.

Missing refresh cookies are allowed so repeated logout remains successful.

**Calls appearing in the body:** `AuthService.logout`, `Cookie`, `Depends`, `router.post`.

## backend/app/schemas/transcription.py

[Open source](../../backend/app/schemas/transcription.py)

### `TranscriptSegment.check_time_order`

[Source line 19](../../backend/app/schemas/transcription.py#L19)

```python
def check_time_order(self)
```

Reject reversed or empty time intervals from the transcription provider.

**Calls appearing in the body:** `ValueError`, `model_validator`.

### `SavedTranscription.size_mb`

[Source line 64](../../backend/app/schemas/transcription.py#L64)

```python
def size_mb(self) -> float
```

Expose decimal megabytes while the database keeps the exact byte count.

**Calls appearing in the body:** `round`.

## backend/app/services/audio.py

[Open source](../../backend/app/services/audio.py)

### `AudioService.receive_upload`

[Source line 27](../../backend/app/services/audio.py#L27)

```python
async def receive_upload(file: UploadFile, language: str | None=None, *, db: AsyncSession, user_id: UUID) -> SavedAudio
```

Copy an upload into a temporary file with a usable filesystem path.

Input: uploaded bytes, authenticated user ID, database session, and language.
Processing: copy and count bytes, inspect the original, then normalize to
mono 16 kHz PCM WAV, detect speech, extract clips, and transcribe them.
Output: file information plus duration, bitrate, sample rate, channels,
codec, container format, speech ranges, and transcription on the original timeline.

The temporary copy exists only inside the with block. It is automatically
closed and deleted afterward, including when an exception occurs.
The original and normalized metadata are returned for comparison.
After processing succeeds, the original is copied to permanent storage
and the completed transcription is committed. Temporary copies are deleted.

**Calls appearing in the body:** `AudioLimitError`, `AudioService.get_normalized_metadata`, `AudioService.validate_duration`, `AudioStorageService.save`, `ReceivedAudio`, `file.read`, `file.seek`, `len`, `round`, `run_in_threadpool`, `temp_file.flush`, `temp_file.write`, `tempfile.NamedTemporaryFile`.

### `AudioService.validate_duration`

[Source line 106](../../backend/app/services/audio.py#L106)

```python
def validate_duration(duration: float) -> None
```

Input seconds → compare with the limit → reject audio that is too long.

**Calls appearing in the body:** `AudioLimitError`.

### `AudioService.get_normalized_metadata`

[Source line 114](../../backend/app/services/audio.py#L114)

```python
async def get_normalized_metadata(input_path: str | Path, language: str | None=None) -> NormalizedAudio
```

Normalize a temporary copy and return its inspected audio properties.

Input: the path of the original audio file, which must still exist.
Processing: normalize, inspect, run VAD, extract clips, and call Groq.
Output: normalized metadata, clip metadata, combined text, and timestamps.

The temporary folder and WAV are deleted when this method exits,
including on failure. The original file is not modified.

**Calls appearing in the body:** `AudioService.validate_duration`, `NormalizedAudio`, `Path`, `TranscriptionService.transcribe_clips`, `metadata.model_dump`, `run_in_threadpool`, `tempfile.TemporaryDirectory`.

## backend/app/services/auth.py

[Open source](../../backend/app/services/auth.py)

### `AuthService.login_with_google`

[Source line 23](../../backend/app/services/auth.py#L23)

```python
async def login_with_google(db: AsyncSession, response: Response, credential: str) -> dict
```

Verify a Google ID token, find/create its user, and establish a session.

Use db for repository operations and response for HttpOnly cookies.
Persist a refresh-token hash, commit it, then set both cookies and return
a success message. UserRepository.create currently commits new users
separately. Invalid Google credentials raise ValueError; the route
converts that error to HTTP 401.

**Calls appearing in the body:** `AuthService.set_auth_cookies`, `RefreshSessionRepository.create`, `UserRepository.create`, `UserRepository.get_by_google_id`, `ValueError`, `create_access_token`, `db.commit`, `generate_refresh_token`, `get_refresh_token_expiry`, `google_user.get`, `hash_refresh_token`, `id_token.verify_oauth2_token`, `requests.Request`.

### `AuthService.set_auth_cookies`

[Source line 85](../../backend/app/services/auth.py#L85)

```python
def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None
```

Attach access and refresh tokens to response as HttpOnly cookies.

Use configured security flags and lifetimes. The access cookie applies
to /; the refresh cookie is restricted to /auth. No database writes occur.

**Calls appearing in the body:** `response.set_cookie`.

### `AuthService.get_current_user`

[Source line 114](../../backend/app/services/auth.py#L114)

```python
async def get_current_user(db: AsyncSession, access_token: str) -> User
```

Validate an access JWT and return the User identified by its subject.

Read through db without committing. Raise ValueError when token
validation fails, the subject is invalid, or the user no longer exists.

**Calls appearing in the body:** `UserRepository.get_by_id`, `ValueError`, `decode_access_token`, `uuid.UUID`.

### `AuthService.get_me`

[Source line 144](../../backend/app/services/auth.py#L144)

```python
def get_me(user: User) -> dict
```

Build a public profile dictionary from an already authenticated User.

This helper performs no authentication or database work. The current
/me route builds the same response directly.

### `AuthService.refresh_tokens`

[Source line 158](../../backend/app/services/auth.py#L158)

```python
async def refresh_tokens(db: AsyncSession, response: Response, refresh_token: str | None) -> dict
```

Rotate a valid refresh cookie and return a success message.

Conditionally revoke the matching unexpired session so only one request
can consume it. Stage the replacement hash and commit both changes in
one transaction. Roll back on failure and set response cookies only
after commit. Missing, invalid, expired, or revoked tokens raise HTTP 401.

**Calls appearing in the body:** `AuthService.set_auth_cookies`, `HTTPException`, `RefreshSessionRepository.create`, `RefreshSessionRepository.revoke`, `UserRepository.get_by_id`, `create_access_token`, `db.commit`, `db.rollback`, `generate_refresh_token`, `get_refresh_token_expiry`, `hash_refresh_token`.

### `AuthService.logout`

[Source line 210](../../backend/app/services/auth.py#L210)

```python
async def logout(db: AsyncSession, response: Response, refresh_token: str | None) -> dict
```

Revoke the supplied refresh session and clear both response cookies.

Commit revocation before clearing cookies; roll back database failures.
Missing or already-revoked sessions still succeed. Other sessions are
unaffected, and previously issued access JWTs remain valid until expiry.

**Calls appearing in the body:** `RefreshSessionRepository.revoke`, `db.commit`, `db.rollback`, `hash_refresh_token`, `response.delete_cookie`.

## backend/app/services/exports.py

[Open source](../../backend/app/services/exports.py)

### `subtitle_timestamp`

[Source line 8](../../backend/app/services/exports.py#L8)

```python
def subtitle_timestamp(seconds: float, separator: str) -> str
```

Convert seconds to hours:minutes:seconds plus three millisecond digits.

**Calls appearing in the body:** `divmod`, `round`.

### `render_transcript`

[Source line 17](../../backend/app/services/exports.py#L17)

```python
def render_transcript(job: SavedTranscription, format: Literal['txt', 'srt', 'vtt']) -> str
```

Input saved text/segments → format cues on original timeline → downloadable text.

TXT uses the full transcript. Subtitle formats use each segment's timestamps.
An empty transcript produces empty TXT/SRT or a WebVTT header with no cues.

**Calls appearing in the body:** `' '.join`, `''.join`, `cues.append`, `escape`, `len`, `segment.text.split`, `subtitle_timestamp`.

## backend/app/services/storage.py

[Open source](../../backend/app/services/storage.py)

### `AudioStorageService.save`

[Source line 26](../../backend/app/services/storage.py#L26)

```python
async def save(db: AsyncSession, *, source: str | Path, user_id: UUID, result: ReceivedAudio, size_bytes: int, language: str | None) -> SavedAudio
```

Return the job ID after original audio and transcript are both saved.

Input: successful processing results and a temporary original that still exists.
Processing: copy the file, stage the database row, then commit once.
Output: the existing upload response plus id and COMPLETED status.

Roll back and remove the copied file on failure. Filesystem and database
commits are not atomic across a process crash; this handles normal errors.

**Calls appearing in the body:** `AudioStorageError`, `SavedAudio`, `TranscriptionRepository.create_completed`, `db.commit`, `db.rollback`, `isinstance`, `logger.exception`, `result.model_dump`, `run_in_threadpool`, `uuid4`.

### `AudioStorageService.get_saved`

[Source line 78](../../backend/app/services/storage.py#L78)

```python
async def get_saved(db: AsyncSession, job_id: UUID, user_id: UUID) -> SavedTranscription | None
```

Read one owner's persisted job and return its public representation.

**Calls appearing in the body:** `SavedTranscription.model_validate`, `TranscriptionRepository.get_owned`.

### `AudioStorageService.get_download`

[Source line 86](../../backend/app/services/storage.py#L86)

```python
async def get_download(db: AsyncSession, job_id: UUID, user_id: UUID) -> tuple[Path, str] | None
```

Return an owned original's disk path and safe download filename.

Input: job ID and authenticated user ID.
Processing: check ownership first, then locate the original in storage.
Output: (path, filename), or None for an inaccessible job or missing file.
The HTTP route streams the file; this method does not load audio into RAM.

**Calls appearing in the body:** `''.join`, `TranscriptionRepository.get_owned`, `job.original_filename.replace`, `job.original_filename.replace('\\', '/').rsplit`, `ord`, `run_in_threadpool`.

## backend/app/services/transcription.py

[Open source](../../backend/app/services/transcription.py)

### `TranscriptionService.transcribe_clips`

[Source line 14](../../backend/app/services/transcription.py#L14)

```python
async def transcribe_clips(folder: str | Path, clips: list[SpeechClip], language: str | None=None) -> TranscriptionResult
```

Return combined text, detected languages, and original-timeline segments.

Input: an existing clip folder, ordered clip metadata, and optional language.
Processing: call Groq for each clip and add its original start offset.
Output: TranscriptionResult; an empty clip list makes no external requests.

No partial transcript is returned if any clip fails. This step does not
create database records or preserve files after the upload request ends.

**Calls appearing in the body:** `' '.join`, `GroqProvider.transcribe`, `Path`, `TranscriptSegment`, `TranscriptionProviderError`, `TranscriptionResult`, `languages.append`, `min`, `perf_counter`, `round`, `segments.append`, `sorted`, `texts.append`.

## frontend/src/App.tsx

[Open source](../../frontend/src/App.tsx)

### `App`

[Source line 8](../../frontend/src/App.tsx#L8)

```typescript
App()
```

**Input:** No props; reads browser session on mount.

Owns user, loading, error, loggingOut, and audioBusy state. The mount effect calls loadUser, ignores late results after unmount, and chooses loading, Login, or AudioWorkspace. Audio busy state disables logout.

**Output / side effects:** Rendered top-level UI; session-expired callback clears user and shows the login screen.

### `App.handleLogin`

[Source line 24](../../frontend/src/App.tsx#L24)

```typescript
handleLogin()
```

**Input:** Successful Google sign-in callback.

Calls loadUser to fetch the authenticated account, rejects missing sessions, clears the error, and stores the user.

**Output / side effects:** App transitions to the authenticated workspace; failures propagate to the sign-in button.

### `App.handleLogout`

[Source line 31](../../frontend/src/App.tsx#L31)

```typescript
handleLogout()
```

**Input:** Logout button click.

Sets loggingOut, clears errors, awaits logout, and clears user only on success. Displays a readable error on failure and resets the busy state in finally.

**Output / side effects:** Login screen after successful logout.

## frontend/src/audio.ts

[Open source](../../frontend/src/audio.ts)

### `checkResponse`

[Source line 34](../../frontend/src/audio.ts#L34)

```typescript
checkResponse(response: Response): Promise<void>
```

**Input:** Response from an audio API request.

Returns for success. Otherwise attempts JSON decoding, uses a string detail if available, and falls back to a generic error message.

**Output / side effects:** No value on success; throws Error for failed HTTP responses.

### `uploadAudio`

[Source line 42](../../frontend/src/audio.ts#L42)

```typescript
uploadAudio(file: File, language: string): Promise<SavedJob>
```

**Input:** File and optional language string.

Creates FormData with file and nonblank trimmed language, calls authenticatedFetch for /audio/upload, checks response, and maps nested upload metadata/transcription into the UI SavedJob shape. Lets browser set multipart boundaries.

**Output / side effects:** SavedJob with text, segments, language, size, duration, status, and ID.

### `loadAudioJob`

[Source line 65](../../frontend/src/audio.ts#L65)

```typescript
loadAudioJob(id: string): Promise<SavedJob>
```

**Input:** Saved job ID.

URL-encodes the ID, GETs /audio/{id} with authenticatedFetch, checks errors, and parses JSON.

**Output / side effects:** SavedJob for an owned transcription.

### `downloadAudio`

[Source line 72](../../frontend/src/audio.ts#L72)

```typescript
downloadAudio(id: string): Promise<Blob>
```

**Input:** Saved job ID.

GETs /audio/{id}/download through authenticatedFetch and checkResponse.

**Output / side effects:** Original audio Blob.

### `loadAudioLimits`

[Source line 79](../../frontend/src/audio.ts#L79)

```typescript
loadAudioLimits(): Promise<{ max_size_bytes: number; max_duration_seconds: number }>
```

**Input:** No arguments.

GETs /audio/limits using authenticatedFetch, checks the response, and parses JSON. The backend route itself is public.

**Output / side effects:** max_size_bytes and max_duration_seconds.

### `downloadTranscript`

[Source line 86](../../frontend/src/audio.ts#L86)

```typescript
downloadTranscript(id: string, format: "txt" | "srt" | "vtt"): Promise<Blob>
```

**Input:** Job ID and txt/srt/vtt format.

GETs /audio/{id}/export/{format}, checks HTTP errors, and reads a Blob.

**Output / side effects:** Text/subtitle Blob ready for the browser download handler.

## frontend/src/auth.ts

[Open source](../../frontend/src/auth.ts)

### `fetchUser`

[Source line 12](../../frontend/src/auth.ts#L12)

```typescript
fetchUser(): Promise<User | null>
```

**Input:** No arguments; browser cookies and API_URL.

GETs /auth/me. On 401 POSTs /auth/refresh, returns null for refresh 401, rejects other refresh failures, then retries /auth/me once. Final 401 returns null; other non-success responses throw.

**Output / side effects:** User or null, or an account/session error.

### `loadUser`

[Source line 28](../../frontend/src/auth.ts#L28)

```typescript
loadUser(): Promise<User | null>
```

**Input:** No arguments; module-level userRequest/logoutRequest promises.

Shares an in-flight fetchUser request among callers. Waits for an ongoing logout and returns null instead of refreshing. Clears userRequest in finally.

**Output / side effects:** Promise<User | null>; avoids duplicate refreshes from concurrent checks.

### `logout`

[Source line 37](../../frontend/src/auth.ts#L37)

```typescript
logout(): Promise<void>
```

**Input:** No arguments; current browser session.

Shares concurrent logout calls, waits for any pending user/refresh request to finish (ignoring its failure), then POSTs /auth/logout with cookies. Throws on non-success and clears logoutRequest in finally.

**Output / side effects:** Resolved promise after logout or a retryable error.

### `authenticatedFetch`

[Source line 56](../../frontend/src/auth.ts#L56)

```typescript
authenticatedFetch(path: string, options: RequestInit = {}): Promise<Response>
```

**Input:** API path plus optional RequestInit.

Rejects while logout is running. Forces credentials: include, sends the request, and on 401 calls loadUser before retrying the original request once. Missing session or a second 401 throws SessionExpiredError.

**Output / side effects:** Response; non-401 HTTP errors remain for the caller to handle.

## frontend/src/components/AudioRecorder.tsx

[Open source](../../frontend/src/components/AudioRecorder.tsx)

### `AudioRecorder`

[Source line 12](../../frontend/src/components/AudioRecorder.tsx#L12)

```typescript
AudioRecorder({ disabled, limits, onReady, onBusyChange }: Props)
```

**Input:** disabled, limits, onReady, onBusyChange props.

Owns active/error/preview state and recorder/stream/timer refs. Mount cleanup stops capture, clears timeout, and marks component unmounted; preview effect revokes replaced object URLs. Its media-event callbacks assemble the File.

**Output / side effects:** Microphone controls and a local audio preview; onReady passes the recorded File upward.

### `AudioRecorder.start`

[Source line 35](../../frontend/src/components/AudioRecorder.tsx#L35)

```typescript
start()
```

**Input:** Start recording click; configured byte and duration limits.

Prevents duplicate starts, checks browser support, requests microphone access, chooses supported WebM/MP4/Ogg MIME type, registers media callbacks, and starts one-second chunk capture. Clears the previous selected file and schedules duration stop. Releases tracks after cancellation, unmount, or errors.

**Output / side effects:** Active MediaRecorder, chunks collected locally; no audio upload yet.

### `AudioRecorder.stop`

[Source line 103](../../frontend/src/components/AudioRecorder.tsx#L103)

```typescript
stop()
```

**Input:** Stop button, duration timer, or recorder-error path.

Marks the attempt cancelled; stops an active recorder and its media tracks. If microphone permission is still pending, resets UI/busy state so a late stream is released by start.

**Output / side effects:** Recorder's final data and stop events complete file assembly.

## frontend/src/components/AudioWorkspace.tsx

[Open source](../../frontend/src/components/AudioWorkspace.tsx)

### `AudioWorkspace`

[Source line 15](../../frontend/src/components/AudioWorkspace.tsx#L15)

```typescript
AudioWorkspace({ disabled, onBusyChange, onSessionExpired }: Props)
```

**Input:** disabled, onBusyChange, onSessionExpired props.

Owns selected file, language, saved job, job ID, recording/pending state, limits, and feedback. Its mount effect loads server limits; failure is ignored because the server still enforces limits. Forms delegate to upload, lookup, and download handlers.

**Output / side effects:** Recorder, upload form, saved-job lookup, transcript, timestamp list, and downloads.

### `AudioWorkspace.runAction`

[Source line 34](../../frontend/src/components/AudioWorkspace.tsx#L34)

```typescript
runAction(message: string, action: () => Promise<void>)
```

**Input:** Status message and an async action callback.

Returns if disabled or already in flight. Uses a ref to block overlapping actions immediately, resets feedback, marks busy, awaits action, routes SessionExpiredError to App, and resets all busy flags in finally.

**Output / side effects:** Completed action or visible error; no overlapping form requests.

### `AudioWorkspace.handleUpload`

[Source line 54](../../frontend/src/components/AudioWorkspace.tsx#L54)

```typescript
handleUpload(event: FormEvent<HTMLFormElement>)
```

**Input:** Upload form submit and currently selected File/language.

Prevents navigation, rejects missing/empty/oversize files, and uses runAction to await uploadAudio. Stores returned job and ID and displays a success notice.

**Output / side effects:** SavedJob shown in the result section; error feedback if upload fails.

### `AudioWorkspace.handleLookup`

[Source line 71](../../frontend/src/components/AudioWorkspace.tsx#L71)

```typescript
handleLookup(event: FormEvent<HTMLFormElement>)
```

**Input:** Saved-job form submit and jobId text.

Prevents navigation, trims the ID, ignores empty values, and uses runAction to call loadAudioJob.

**Output / side effects:** Existing owned job loaded into the result section.

### `AudioWorkspace.handleDownload`

[Source line 81](../../frontend/src/components/AudioWorkspace.tsx#L81)

```typescript
handleDownload(format?: "txt" | "srt" | "vtt")
```

**Input:** Optional txt/srt/vtt format; current job.

Uses runAction to fetch an original or exported transcript Blob, creates a temporary object URL and download link, clicks and removes the link, then schedules URL revocation after one second.

**Output / side effects:** Browser download and success notice; filenames strip client path components for originals.

## frontend/src/components/GoogleLoginButton.tsx

[Open source](../../frontend/src/components/GoogleLoginButton.tsx)

### `GoogleLoginButton`

[Source line 35](../../frontend/src/components/GoogleLoginButton.tsx#L35)

```typescript
GoogleLoginButton({ onLogin }: { onLogin: () => Promise<void> })
```

**Input:** onLogin callback.

Keeps the latest callback in a ref. On mount, initializes the available Google Identity SDK with VITE_GOOGLE_CLIENT_ID and renders its button. Tracks pending/error feedback; if SDK or button ref is absent, initialization returns.

**Output / side effects:** Google sign-in button and request feedback.

### `GoogleLoginButton.handleCredentialResponse`

[Source line 44](../../frontend/src/components/GoogleLoginButton.tsx#L44)

```typescript
handleCredentialResponse(response: GoogleCredentialResponse)
```

**Input:** GoogleCredentialResponse containing a credential string.

POSTs JSON to API_URL + /auth/google with cookies included, checks HTTP success, then awaits the latest App onLogin callback. Catches errors and clears pending in finally.

**Output / side effects:** Login cookies from backend and refreshed App user state, or a visible login error.

## frontend/src/pages/Login.tsx

[Open source](../../frontend/src/pages/Login.tsx)

### `Login`

[Source line 4](../../frontend/src/pages/Login.tsx#L4)

```typescript
Login({ onLogin }: { onLogin: () => Promise<void> })
```

**Input:** onLogin callback from App.

Renders the login screen and GoogleLoginButton; forwards the callback. Decorative feature cards and waveform have no processing logic.

**Output / side effects:** Google sign-in UI.
