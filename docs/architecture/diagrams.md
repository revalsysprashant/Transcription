# Application diagrams

Each diagram also has standalone `.mmd`, `.svg`, and `.png` files. Arrows show control or data flow; their labels distinguish the two.

## 01 · Entire app

Read top to bottom: browser actions become authenticated API calls, then stored results.

```mermaid
flowchart TB
  user["User<br/>Sign in · record · upload"]:::ui
  react["React application<br/>App + AudioWorkspace"]:::ui
  google["Google Identity<br/>Browser credential / verified identity"]:::external
  proxy["Caddy / same origin<br/>HTTPS in production"]:::infra
  auth["Authentication<br/>Google login · JWT · refresh rotation"]:::auth
  api["Audio routes<br/>Authenticated owner checks"]:::api
  processing["Audio processing<br/>FFprobe → FFmpeg → Silero"]:::process
  groq["Groq Whisper<br/>Transcribe speech clips"]:::external
  storage["Save completed job<br/>Copy original + commit transcript"]:::data
  db["PostgreSQL<br/>Users · sessions · transcriptions"]:::data
  disk["Persistent audio volume<br/>Original recordings only"]:::data
  result["Result in browser<br/>Transcript · timestamps · exports"]:::ui
  user -->|"interacts"| react
  react -->|"sign in"| google
  react -->|"HTTP + cookies"| proxy
  proxy -->|"/auth/*"| auth
  proxy -->|"/audio/*"| api
  google -->|"credential verification"| auth
  auth -->|"users + session hashes"| db
  api -->|"upload"| processing
  processing -->|"speech WAV clips"| groq
  groq -->|"validated text + times"| storage
  processing -->|"no speech: empty result"| storage
  storage -->|"COMPLETED row"| db
  storage -->|"original bytes"| disk
  storage -->|"upload response via API"| result
  api -->|"owned job / original / export"| result
  classDef ui fill:#dbeafe,stroke:#475569,color:#0f172a
  classDef auth fill:#ede9fe,stroke:#475569,color:#0f172a
  classDef api fill:#cffafe,stroke:#475569,color:#0f172a
  classDef process fill:#fef3c7,stroke:#475569,color:#0f172a
  classDef external fill:#ffe4e6,stroke:#475569,color:#0f172a
  classDef data fill:#dcfce7,stroke:#475569,color:#0f172a
  classDef infra fill:#e2e8f0,stroke:#475569,color:#0f172a
  classDef error fill:#fee2e2,stroke:#475569,color:#0f172a
```

## 02 · Login and access checks

Session tokens use HttpOnly cookies; only refresh-token hashes are persisted.

```mermaid
flowchart TB
  mount["App mount<br/>loadUser() → fetchUser()"]:::ui
  me["GET /auth/me<br/>get_me() route"]:::api
  dep["get_current_user() dependency<br/>Read access_token cookie"]:::auth
  valid["AuthService.get_current_user()<br/>decode_access_token() + UUID subject"]:::auth
  lookup["UserRepository.get_by_id()<br/>Return user or reject"]:::data
  profile["Public user profile<br/>App renders AudioWorkspace"]:::ui
  login["Login + GoogleLoginButton<br/>Google supplies credential"]:::ui
  post["handleCredentialResponse()<br/>POST /auth/google"]:::ui
  verify["AuthService.login_with_google()<br/>Verify Google token + audience"]:::auth
  find["get_by_google_id()<br/>create() if new; user insert commits"]:::data
  tokens["create_access_token()<br/>generate_refresh_token()<br/>hash_refresh_token() + expiry"]:::auth
  session["RefreshSessionRepository.create()<br/>Flush hash → service commits"]:::data
  cookies["set_auth_cookies()<br/>Access path / · refresh path /auth"]:::auth
  fail["Invalid access / identity<br/>401 → refresh or sign-in screen"]:::error
  mount -->|"session check"| me
  me -->|"Depends"| dep
  dep -->|"cookie present"| valid
  valid -->|"valid JWT"| lookup
  lookup -->|"existing user"| profile
  dep -->|"missing cookie"| fail
  valid -->|"invalid token"| fail
  lookup -->|"missing user"| fail
  login -->|"callback"| post
  post -->|"credential"| verify
  verify -->|"verified identity"| find
  verify -->|"invalid Google token"| fail
  find -->|"user UUID"| tokens
  tokens -->|"only token hash"| session
  session -->|"after commit"| cookies
  cookies -->|"handleLogin() rechecks user"| mount
  classDef ui fill:#dbeafe,stroke:#475569,color:#0f172a
  classDef auth fill:#ede9fe,stroke:#475569,color:#0f172a
  classDef api fill:#cffafe,stroke:#475569,color:#0f172a
  classDef process fill:#fef3c7,stroke:#475569,color:#0f172a
  classDef external fill:#ffe4e6,stroke:#475569,color:#0f172a
  classDef data fill:#dcfce7,stroke:#475569,color:#0f172a
  classDef infra fill:#e2e8f0,stroke:#475569,color:#0f172a
  classDef error fill:#fee2e2,stroke:#475569,color:#0f172a
```

## 03 · Refresh, retry, and logout

Concurrent browser checks share one promise; one refresh token can be consumed only once.

```mermaid
flowchart TB
  fetch["authenticatedFetch(path, options)<br/>Send cookies with request"]:::ui
  first["Response status"]:::api
  load["loadUser() / fetchUser()<br/>Share in-flight user check"]:::ui
  refresh["POST /auth/refresh<br/>AuthService.refresh_tokens()"]:::auth
  revoke["hash_refresh_token() → revoke()<br/>Conditional UPDATE, active_only=True"]:::data
  replace["get_by_id() + new token pair<br/>create() replacement hash"]:::auth
  commit["Commit rotation atomically<br/>Set cookies only after commit"]:::data
  recheck["Retry GET /auth/me once<br/>Then retry original request once"]:::ui
  expired["401 after recovery<br/>SessionExpiredError → sign in"]:::error
  rollback["Rollback rotation<br/>No replacement cookies"]:::error
  ok["Return response<br/>Caller checks non-401 errors"]:::ui
  out["logout() frontend<br/>Wait for pending user request"]:::ui
  serverout["POST /auth/logout<br/>Revoke supplied refresh session"]:::auth
  clear["Commit → delete cookies<br/>Other sessions unaffected"]:::auth
  fetch -->|"request"| first
  first -->|"not 401"| ok
  first -->|"401"| load
  load -->|"/auth/me also 401"| refresh
  load -->|"/auth/me valid"| recheck
  refresh -->|"refresh cookie"| revoke
  revoke -->|"unexpired, not revoked"| replace
  revoke -->|"missing / invalid / expired"| rollback
  replace -->|"replacement staged"| commit
  replace -->|"DB failure"| rollback
  commit -->|"new cookies"| recheck
  recheck -->|"success"| ok
  recheck -->|"401"| expired
  rollback -->|"401; other errors surface"| expired
  out -->|"avoid refresh/logout race"| serverout
  serverout -->|"revocation committed"| clear
  classDef ui fill:#dbeafe,stroke:#475569,color:#0f172a
  classDef auth fill:#ede9fe,stroke:#475569,color:#0f172a
  classDef api fill:#cffafe,stroke:#475569,color:#0f172a
  classDef process fill:#fef3c7,stroke:#475569,color:#0f172a
  classDef external fill:#ffe4e6,stroke:#475569,color:#0f172a
  classDef data fill:#dcfce7,stroke:#475569,color:#0f172a
  classDef infra fill:#e2e8f0,stroke:#475569,color:#0f172a
  classDef error fill:#fee2e2,stroke:#475569,color:#0f172a
```

## 04 · Browser recording and UI

Recording is local. Stopping creates a File; transcription begins only on Upload and transcribe.

```mermaid
flowchart TB
  app["App()<br/>User / loading / logout / audioBusy"]:::ui
  workspace["AudioWorkspace()<br/>File · language · job · pending · errors"]:::ui
  limits["loadAudioLimits()<br/>GET /audio/limits"]:::api
  start["AudioRecorder.start()<br/>Check support → getUserMedia()"]:::ui
  rec["MediaRecorder<br/>Choose WebM / MP4 / Ogg<br/>Emit chunks every 1000 ms"]:::ui
  data["ondataavailable<br/>Count bytes; collect chunks"]:::ui
  stop["stop() / duration timer<br/>Stop recorder and media tracks"]:::ui
  final["onstop<br/>Blob → File → preview URL<br/>onReady(file)"]:::ui
  choose["File picker onChange<br/>setFile(selected file)"]:::ui
  upload["handleUpload()<br/>Validate nonempty file and size"]:::ui
  action["runAction()<br/>Prevent overlap; set pending; catch errors"]:::ui
  send["uploadAudio()<br/>FormData file + optional language"]:::api
  render["setJob() + setJobId()<br/>Render results and saved-job notice"]:::ui
  error["Microphone / size / recording error<br/>Show feedback; release tracks"]:::error
  clean["Unmount / preview cleanup<br/>Clear timer · stop tracks<br/>Revoke obsolete object URLs"]:::ui
  app -->|"props + callbacks"| workspace
  workspace -->|"mount effect"| limits
  workspace -->|"record button"| start
  limits -->|"size limit"| data
  limits -->|"duration limit"| stop
  start -->|"permission granted"| rec
  start -->|"denied / unsupported"| error
  rec -->|"encoded chunks"| data
  data -->|"manual stop / size limit"| stop
  stop -->|"final data event then stop event"| final
  data -->|"too large"| error
  final -->|"recorded File selected"| upload
  choose -->|"uploaded File selected"| upload
  upload -->|"valid file"| action
  action -->|"await request"| send
  send -->|"SavedJob"| render
  rec -->|"unmount"| clean
  final -->|"preview replaced"| clean
  classDef ui fill:#dbeafe,stroke:#475569,color:#0f172a
  classDef auth fill:#ede9fe,stroke:#475569,color:#0f172a
  classDef api fill:#cffafe,stroke:#475569,color:#0f172a
  classDef process fill:#fef3c7,stroke:#475569,color:#0f172a
  classDef external fill:#ffe4e6,stroke:#475569,color:#0f172a
  classDef data fill:#dcfce7,stroke:#475569,color:#0f172a
  classDef infra fill:#e2e8f0,stroke:#475569,color:#0f172a
  classDef error fill:#fee2e2,stroke:#475569,color:#0f172a
```

## 05 · Audio processing pipeline

All steps finish inside POST /audio/upload; blocking audio work runs in a thread pool.

```mermaid
flowchart TB
  route["receive_audio() route<br/>Auth + multipart validation"]:::api
  receive["AudioService.receive_upload()<br/>Copy 64 KiB chunks into temp file"]:::process
  probe["probe_audio()<br/>FFprobe metadata → AudioMetadata"]:::process
  fallback["measure_packet_duration()<br/>Scan packets for duration-less WebM"]:::process
  duration["validate_duration()<br/>Reject audio longer than limit"]:::process
  normalize["get_normalized_metadata()<br/>normalize_audio(): FFmpeg WAV"]:::process
  reprobe["probe_audio(normalized WAV)<br/>Recheck decoded duration"]:::process
  vad["detect_speech()<br/>PCM → float samples → Silero<br/>Cached ONNX model, guarded by lock"]:::process
  clips["extract_speech_clips()<br/>Copy ordered speech ranges to WAVs"]:::process
  transcribe["TranscriptionService.transcribe_clips()<br/>Sequential clip requests"]:::process
  provider["GroqProvider.transcribe()<br/>create_groq_client() → verbose JSON<br/>Validate ClipTranscription"]:::external
  merge["Merge text + unique languages<br/>Clamp clip ends; add original offsets"]:::process
  empty["No speech ranges<br/>Empty transcript; no Groq calls"]:::process
  save["AudioStorageService.save()<br/>Persist original + COMPLETED job"]:::data
  cleanup["Return SavedAudio / error<br/>Delete temporary files; close upload"]:::api
  errors["Errors returned by route<br/>400 bad audio · 413 limit<br/>502 provider · 503 unavailable<br/>500 storage; 422 request validation"]:::error
  route -->|"authenticated request"| receive
  receive -->|"under size limit"| probe
  probe -->|"missing duration"| fallback
  fallback -->|"packet span"| duration
  probe -->|"duration available"| duration
  duration -->|"within limit"| normalize
  normalize -->|"mono 16 kHz PCM"| reprobe
  reprobe -->|"decoded length valid"| vad
  vad -->|"speech ranges"| clips
  clips -->|"temporary clips"| transcribe
  transcribe -->|"each clip"| provider
  provider -->|"validated response"| merge
  transcribe -->|"zero clips"| empty
  merge -->|"full result"| save
  empty -->|"successful no-speech result"| save
  save -->|"commit successful"| cleanup
  receive -->|"oversize"| errors
  provider -->|"missing key / provider error"| errors
  normalize -->|"decode / tool error"| errors
  errors -->|"finally"| cleanup
  classDef ui fill:#dbeafe,stroke:#475569,color:#0f172a
  classDef auth fill:#ede9fe,stroke:#475569,color:#0f172a
  classDef api fill:#cffafe,stroke:#475569,color:#0f172a
  classDef process fill:#fef3c7,stroke:#475569,color:#0f172a
  classDef external fill:#ffe4e6,stroke:#475569,color:#0f172a
  classDef data fill:#dcfce7,stroke:#475569,color:#0f172a
  classDef infra fill:#e2e8f0,stroke:#475569,color:#0f172a
  classDef error fill:#fee2e2,stroke:#475569,color:#0f172a
```

## 06 · Persistence, retrieval, and export

The authenticated user ID is included in every saved-job lookup.

```mermaid
flowchart TB
  save["AudioStorageService.save()<br/>Generate UUID + SavedAudio response"]:::data
  copy["StorageRepository.save_original()<br/>Exclusive file creation<br/>user UUID / job UUID.audio"]:::data
  insert["TranscriptionRepository.create_completed()<br/>Exact bytes + JSON segments<br/>Flush COMPLETED row"]:::data
  commit["db.commit()<br/>Return upload result"]:::data
  undo["Failure compensation<br/>Rollback + remove_original()<br/>AudioStorageError"]:::error
  lookup["handleLookup() → loadAudioJob()<br/>GET /audio/{job_id}"]:::ui
  get["get_saved_audio() → get_saved()<br/>get_owned(job_id, user_id)"]:::api
  saved["SavedTranscription<br/>size_mb computed; internal path omitted"]:::data
  download["handleDownload()<br/>downloadAudio() / downloadTranscript()"]:::ui
  original["download_audio() → get_download()<br/>get_owned() then get_original_path()<br/>Sanitize download filename"]:::api
  export["export_transcript() → get_saved()<br/>render_transcript()"]:::api
  format["TXT: full text<br/>SRT / VTT: subtitle_timestamp()<br/>Escape cue text, skip zero-length cues"]:::process
  blob["Response blob → object URL<br/>Temporary download link<br/>Revoke URL after starting download"]:::ui
  missing["404<br/>Not owned / missing record<br/>Original missing on disk"]:::error
  save -->|"temporary original"| copy
  copy -->|"relative storage key"| insert
  insert -->|"staged row"| commit
  copy -->|"normal copy failure"| undo
  insert -->|"DB failure"| undo
  lookup -->|"job ID"| get
  get -->|"owned"| saved
  get -->|"not found"| missing
  download -->|"original bytes"| original
  download -->|"txt / srt / vtt"| export
  original -->|"FileResponse"| blob
  original -->|"not accessible"| missing
  export -->|"owned transcript"| format
  export -->|"not found"| missing
  format -->|"UTF-8 response"| blob
  classDef ui fill:#dbeafe,stroke:#475569,color:#0f172a
  classDef auth fill:#ede9fe,stroke:#475569,color:#0f172a
  classDef api fill:#cffafe,stroke:#475569,color:#0f172a
  classDef process fill:#fef3c7,stroke:#475569,color:#0f172a
  classDef external fill:#ffe4e6,stroke:#475569,color:#0f172a
  classDef data fill:#dcfce7,stroke:#475569,color:#0f172a
  classDef infra fill:#e2e8f0,stroke:#475569,color:#0f172a
  classDef error fill:#fee2e2,stroke:#475569,color:#0f172a
```

## 07 · Startup and production deployment

Production configuration is prepared; this diagram does not imply an AWS deployment exists.

```mermaid
flowchart TB
  env["Environment setup<br/>init-env.py → .env.production<br/>DOMAIN + Google/Groq + new secrets"]:::infra
  package["package.sh<br/>Source archive; no secrets or audio"]:::infra
  server["Future Ubuntu server<br/>install-docker-ubuntu.sh"]:::infra
  compose["compose.production.yml<br/>Build images and start services"]:::infra
  db["PostgreSQL 17<br/>pg_isready health check"]:::data
  migrate["alembic upgrade head<br/>Users + transcriptions → sessions"]:::data
  api["Uvicorn → FastAPI<br/>get_settings() + get_db()<br/>/health confirms process only"]:::api
  web["Caddy<br/>Static Vite build + API proxy<br/>Starts after backend healthy"]:::infra
  dns["Public domain + DNS<br/>Ports 80 / 443 reachable<br/>Google authorized HTTPS origin"]:::external
  tls["Automatic HTTPS<br/>Certificates persist in volume<br/>Secure cookies enabled"]:::auth
  volumes["Named volumes<br/>Database · audio · certificates<br/>Survive container replacement"]:::data
  local["Local Docker alternative<br/>127.0.0.1:8080 → Caddy :80<br/>Separate DB; cookie_secure=false"]:::infra
  shutdown["lifespan() shutdown<br/>Dispose database engine"]:::api
  env -->|"configuration"| compose
  package -->|"copy archive + env separately"| server
  server -->|"Docker installed"| compose
  compose -->|"start first"| db
  db -->|"healthy"| migrate
  migrate -->|"migration success"| api
  api -->|"healthy"| web
  dns -->|"certificate prerequisites"| tls
  tls -->|"HTTPS origin"| web
  db -->|"database"| volumes
  api -->|"original audio"| volumes
  web -->|"certificates"| volumes
  compose -->|"use compose.yml for local run"| local
  api -->|"process shutdown"| shutdown
  classDef ui fill:#dbeafe,stroke:#475569,color:#0f172a
  classDef auth fill:#ede9fe,stroke:#475569,color:#0f172a
  classDef api fill:#cffafe,stroke:#475569,color:#0f172a
  classDef process fill:#fef3c7,stroke:#475569,color:#0f172a
  classDef external fill:#ffe4e6,stroke:#475569,color:#0f172a
  classDef data fill:#dcfce7,stroke:#475569,color:#0f172a
  classDef infra fill:#e2e8f0,stroke:#475569,color:#0f172a
  classDef error fill:#fee2e2,stroke:#475569,color:#0f172a
```

## 08 · Stored data and API shapes

Schema has multiple status values, but the current upload flow persists only COMPLETED jobs.

```mermaid
flowchart TB
  user["users<br/>id UUID PK · google_id unique<br/>email · name · avatar · timestamps"]:::data
  session["refresh_sessions<br/>id UUID PK · user_id FK<br/>token_hash unique · expires_at<br/>revoked_at · created_at"]:::data
  job["transcriptions<br/>id UUID PK · user_id FK<br/>original_storage_key · exact bytes<br/>text · segments JSONB · language<br/>status · duration · processing time"]:::data
  file["Original audio file<br/>user_id / job_id.audio<br/>Stored outside PostgreSQL"]:::data
  meta["AudioMetadata<br/>Positive finite duration<br/>sample rate · channels · codec"]:::api
  normalized["NormalizedAudio<br/>Metadata + speech ranges / clips<br/>TranscriptionResult"]:::api
  response["SavedAudio upload response<br/>ReceivedAudio + id + status"]:::api
  public["SavedTranscription retrieval<br/>Public metadata + size_mb<br/>No internal storage key"]:::api
  segment["TranscriptSegment<br/>Nonempty text · finite times<br/>check_time_order(): end &gt; start"]:::api
  clip["ClipTranscription<br/>Nonempty text + segments<br/>Optional detected language"]:::api
  statuses["Enum: UPLOADED / PROCESSING<br/>COMPLETED / FAILED<br/>No persisted progress transitions yet"]:::error
  user -->|"one to many"| session
  user -->|"one to many"| job
  job -->|"relative storage key"| file
  meta -->|"extends metadata"| normalized
  normalized -->|"nested result"| response
  job -->|"model_validate(from_attributes)"| public
  segment -->|"one or more segments"| clip
  clip -->|"merged with original offsets"| normalized
  statuses -->|"status column"| job
  classDef ui fill:#dbeafe,stroke:#475569,color:#0f172a
  classDef auth fill:#ede9fe,stroke:#475569,color:#0f172a
  classDef api fill:#cffafe,stroke:#475569,color:#0f172a
  classDef process fill:#fef3c7,stroke:#475569,color:#0f172a
  classDef external fill:#ffe4e6,stroke:#475569,color:#0f172a
  classDef data fill:#dcfce7,stroke:#475569,color:#0f172a
  classDef infra fill:#e2e8f0,stroke:#475569,color:#0f172a
  classDef error fill:#fee2e2,stroke:#475569,color:#0f172a
```
