You are continuing development of an existing full-stack AI audio transcription application.

Your job is to inspect the existing repository first, understand what is already implemented, preserve the current architecture and conventions, and then continue building the application incrementally.

Do not redesign the project unless absolutely necessary.

Do not blindly overwrite existing code.

Do not build the whole application in one pass.

The repository is the source of truth for what currently exists.

---

# 1. PROJECT GOAL

Build a production-shaped AI audio transcription application.

Authenticated users should be able to:

- sign in with Google
- upload audio
- record audio from the browser
- optionally choose a transcription language
- use automatic language detection
- submit audio for transcription
- see job status
- receive transcript text
- receive timestamps / segments
- see detected language
- see audio duration
- see processing time
- download/export transcripts

The application should eventually support asynchronous background processing, WebSocket status updates, and production storage, but those must be introduced incrementally.

---

# 2. CORE ASSIGNMENT REQUIREMENTS

## Audio Input

Support:

- uploaded audio files
- browser-recorded audio

Validate:

- file type
- file size
- audio duration

Do not trust MIME type alone.

---

## Audio Processing

Normalize audio into a standard processing format:

```text
uploaded audio
→ decode
→ mono
→ 16 kHz
→ PCM WAV
```

Use FFmpeg / FFprobe.

Do not aggressively preprocess audio by default.

Avoid automatically adding:

- heavy denoising
- high-pass filtering
- DC removal
- aggressive silence trimming
- unnecessary loudness manipulation

Only add those if actual audio quality requirements justify them.

---

## Speech Detection

The assignment explicitly requires identifying human speech and ignoring silence/non-speech.

Use VAD.

Preferred:

```text
Silero VAD
```

unless the existing repository already uses another appropriate implementation.

---

## Transcription

Use a speech-to-text provider.

Current planned provider:

```text
Groq / Whisper
```

Support:

- specified language
- automatic language detection

Keep the STT provider behind a provider abstraction so it can be changed later.

---

## Transcript Processing

The application should:

- maintain segment order
- combine segment text
- preserve timestamps where supported
- store segments as JSONB
- generate final transcript text

---

## Quality Validation

Handle:

- empty transcripts
- invalid audio
- provider failures
- unclear / unusable transcription results
- malformed provider responses

Fail gracefully with useful sanitized errors.

---

## Output

Final transcription data should include:

- transcript text
- detected language
- audio duration
- processing time
- timestamped segments
- status
- downloadable/exportable transcript

---

# 3. TECH STACK

## Backend

Use:

- Python 3.12
- FastAPI
- SQLAlchemy 2.0 async
- asyncpg
- PostgreSQL
- Alembic async
- Pydantic v2
- pydantic-settings
- Google Identity authentication
- JWT access tokens
- opaque refresh tokens
- HttpOnly cookies
- FFmpeg
- FFprobe
- Groq API
- Redis later
- Celery later
- WebSockets later
- local storage initially
- S3-compatible storage later

---

## Frontend

Use:

- React
- TypeScript
- Vite
- pnpm
- Tailwind CSS
- Google Identity Services

---

## Development

Use:

- uv for Python environment / execution
- requirements.txt
- uv.lock
- Zed editor/debugger
- Docker Compose for PostgreSQL
- FastAPI currently runs locally, not inside Docker

---

# 4. STRICT DEVELOPMENT WORKFLOW

This is a hard requirement.

Build **one functionality at a time**.

Do not make giant commits.

Do not produce 5,000–10,000 line changes.

Every implementation cycle must be a small reviewable unit.

Use this workflow:

```text
inspect repository
→ define ONE current functionality
→ explain scope briefly
→ implement only that functionality
→ run relevant checks/tests
→ report what changed
→ STOP
```

After completing one functionality, wait for explicit instruction before continuing.

Do not automatically move to the next feature.

---

# 5. SCOPE RULE

Before editing code, state the current scope in one sentence.

Example:

```text
Current scope: implement authenticated audio upload and create an UPLOADED transcription record.
```

Only modify code required for that scope.

If you discover unrelated improvements:

- mention them
- do not implement them
- leave them for another task

Exception: fix something unrelated only if it blocks the current functionality.

---

# 6. COMMIT-SIZED CHANGES

Think of each task as one clean Git commit.

A reasonable task may involve:

```text
1 route
1 service method
1–2 repository methods
1 schema
small test changes
```

A bad task would implement all of these at once:

```text
upload
FFmpeg
FFprobe
VAD
Groq
Celery
Redis
WebSockets
S3
dashboard
download system
error framework
```

Do not do that.

---

# 7. NO PREMATURE INFRASTRUCTURE

Do not add infrastructure just because it may be useful later.

For example, while implementing audio upload, do not also add:

```text
Celery
Redis
WebSockets
MinIO
S3
VAD
Groq
```

unless the current feature specifically requires them.

---

# 8. NO OPPORTUNISTIC REFACTORS

Do not refactor unrelated working code while implementing a feature.

Do not rename or reorganize code purely based on personal preference.

Preserve working architecture.

---

# 9. BACKEND ARCHITECTURE CONVENTION

The project uses:

```text
Route
  ↓
Service
  ↓
Repository
  ↓
Database
```

Do not introduce a controller layer.

This convention must remain consistent.

---

# 10. ROUTE RESPONSIBILITIES

Routes should remain thin.

Routes may handle:

- path
- HTTP method
- FastAPI dependencies
- request schemas
- cookie extraction
- calling services
- converting service/domain errors to HTTP errors

Routes should not contain:

- business logic
- SQLAlchemy queries
- transcription workflow logic

---

# 11. SERVICE RESPONSIBILITIES

Services contain business/application logic.

Examples:

- login workflow
- refresh-token rotation
- cookie handling
- audio upload coordination
- audio validation coordination
- transcription orchestration
- storage coordination
- provider coordination

For this application, it is acceptable for services to depend on FastAPI `Response`.

The developer prefers authentication cookie handling inside `AuthService`.

Do not move cookie handling back into routes unless explicitly asked.

---

# 12. REPOSITORY RESPONSIBILITIES

Repositories contain database-access logic only.

Use SQLAlchemy 2.0 async.

Examples:

```python
select(...)
update(...)
db.add(...)
```

Repositories must not contain HTTP logic.

For multi-step atomic operations, repositories should not independently commit unless the operation is truly standalone.

The service should own the transaction boundary when multiple DB operations must succeed together.

---

# 13. SQLALCHEMY RULES

Use SQLAlchemy 2.0 syntax only.

Use:

```python
Mapped
mapped_column
DeclarativeBase
AsyncSession
async_sessionmaker
select
update
```

Do not use:

```python
session.query(...)
```

Do not use raw SQL for normal application queries.

The async database session variable must always be named:

```python
db
```

Do not rename it to `session`.

---

# 14. EXISTING BACKEND STRUCTURE

Preserve the existing repository.

Expected structure is approximately:

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   └── utils/
│   │       └── tokens.py
│   ├── models/
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── transcription.py
│   │   ├── refresh_session.py
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── user.py
│   │   └── transcription.py
│   ├── repositories/
│   │   ├── user.py
│   │   ├── refresh_session.py
│   │   └── transcription.py
│   ├── services/
│   │   ├── auth.py
│   │   ├── audio.py
│   │   ├── transcription.py
│   │   └── speech_detection.py
│   ├── providers/
│   │   └── groq.py
│   ├── routes/
│   │   ├── auth.py
│   │   └── transcriptions.py
│   ├── workers/
│   └── websocket/
├── alembic/
├── alembic.ini
├── compose.yaml
├── requirements.txt
├── pyproject.toml
├── uv.lock
├── .env
└── .env.example
```

Do not create duplicate directories if equivalent structure already exists.

Inspect before changing anything.

---

# 15. CONFIGURATION

Backend environment variables are approximately:

```env
DATABASE_URL=postgresql+asyncpg://transcription:transcription@localhost:5433/transcription_db

APP_NAME=Transcription API
APP_ENV=development
DEBUG=true

GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com

JWT_SECRET=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

COOKIE_SECURE=false
COOKIE_SAMESITE=lax
```

`config.py` should expose configuration using `pydantic-settings`.

Do not hardcode secrets.

Production later should use:

```env
COOKIE_SECURE=true
```

---

# 16. DATABASE ENVIRONMENT

PostgreSQL currently runs in Docker Compose.

Host connection:

```text
localhost:5433
```

Container connection:

```text
postgres:5432
```

The FastAPI app currently runs outside Docker, so it should use:

```text
localhost:5433
```

Conceptual PostgreSQL settings:

```text
POSTGRES_USER=transcription
POSTGRES_PASSWORD=transcription
POSTGRES_DB=transcription_db
```

---

# 17. DATABASE MODELS

Important models:

```text
User
Transcription
RefreshSession
```

---

# 18. USER MODEL

Google-only authentication.

No password.

Conceptual fields:

```text
id
google_id
email
name
avatar_url
created_at
```

Relationships:

```text
User 1:N Transcription
User 1:N RefreshSession
```

Google stable identity must use:

```python
google_payload["sub"]
```

Do not use email as the stable external identity.

---

# 19. TRANSCRIPTION MODEL

One row represents one transcription job.

Conceptual fields:

```text
id UUID PK
user_id UUID FK users.id
original_filename
original_storage_key
mime_type
file_size_bytes
duration_seconds
status
requested_language
detected_language
transcript_text
segments JSONB
processing_time_ms
error_message
created_at
completed_at
```

Current statuses:

```text
UPLOADED
PROCESSING
COMPLETED
FAILED
```

Do not add many status values unless a real requirement appears.

Do not create a transcript segment table.

Use JSONB:

```json
[
    {
        "start": 0.0,
        "end": 3.2,
        "text": "Hello world"
    }
]
```

Do not store audio bytes in PostgreSQL.

Store only a path / storage key.

---

# 20. REFRESH SESSION MODEL

Refresh sessions support:

- multiple browsers/devices
- revocation
- rotation
- logout
- future revoke-all functionality

Conceptual fields:

```text
id UUID
user_id UUID FK
token_hash String(64)
expires_at timestamptz
revoked_at nullable timestamptz
created_at timestamptz
```

Never store raw refresh tokens in the DB.

---

# 21. AUTHENTICATION ARCHITECTURE

Google authentication flow:

```text
React
→ Google Identity Services
→ Google ID token
→ POST /auth/google
→ FastAPI verifies Google token
→ find/create user
→ create access JWT
→ create opaque refresh token
→ hash refresh token
→ save RefreshSession
→ set HttpOnly cookies
```

---

# 22. GOOGLE TOKEN VERIFICATION

Use:

```python
from google.auth.transport import requests
from google.oauth2 import id_token

google_user = id_token.verify_oauth2_token(
    credential,
    requests.Request(),
    settings.google_client_id,
)
```

Use:

```python
google_user["sub"]
```

as `google_id`.

---

# 23. ACCESS TOKEN

Access token:

- JWT
- approximately 15-minute lifetime
- stored in HttpOnly cookie
- contains user UUID in `sub`
- contains token type `"access"`

---

# 24. REFRESH TOKEN

Refresh token:

- opaque random token
- generated with `secrets.token_urlsafe(...)`
- approximately 7-day lifetime
- raw token exists only in browser HttpOnly cookie
- SHA-256 hash stored in PostgreSQL

Do not convert refresh tokens to JWT unless explicitly requested.

---

# 25. TOKEN UTILITIES

Token utilities belong in:

```text
app/core/utils/tokens.py
```

Expected functions:

```python
create_access_token(...)
decode_access_token(...)
generate_refresh_token(...)
hash_refresh_token(...)
get_refresh_token_expiry(...)
```

Use SHA-256 for opaque refresh-token hashing.

Do not use bcrypt or Argon2 for these high-entropy refresh tokens.

---

# 26. AUTH COOKIE SETTINGS

Access cookie:

```text
name: access_token
httponly: true
secure: config-driven
samesite: config-driven
path: /
```

Refresh cookie:

```text
name: refresh_token
httponly: true
secure: config-driven
samesite: config-driven
path: /auth
```

Cookie logic belongs inside `AuthService`.

Frontend requests should use:

```ts
credentials: "include";
```

---

# 27. CORS

For development:

```python
allow_origins=["http://localhost:5173"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

Do not use wildcard origin together with credentials.

Use consistent hostnames:

```text
frontend: http://localhost:5173
backend:  http://localhost:8000
```

Do not mix localhost and 127.0.0.1.

---

# 28. AUTH ROUTES

Expected routes:

```text
POST /auth/google
POST /auth/refresh
POST /auth/logout
GET  /auth/me
```

---

# 29. /AUTH/GOOGLE

Expected input:

```json
{
    "credential": "GOOGLE_ID_TOKEN"
}
```

Service flow:

```text
verify Google token
→ get sub/email/name/picture
→ find user by google_id
→ create user if missing
→ create access JWT
→ create opaque refresh token
→ hash refresh token
→ create RefreshSession
→ set cookies
→ return success response
```

---

# 30. /AUTH/ME

FastAPI dependency should live in:

```text
app/core/dependencies.py
```

The dependency should:

```text
read access_token cookie
→ call AuthService.get_current_user(...)
```

It should not call repositories directly.

Maintain:

```text
dependency
→ AuthService
→ UserRepository
→ DB
```

AuthService should:

```text
decode token
→ validate type == access
→ extract sub
→ convert sub to UUID
→ UserRepository.get_by_id(...)
→ return User
```

---

# 31. REFRESH TOKEN ROTATION — CRITICAL

Refresh-token rotation must be concurrency-safe and atomic.

Do not do:

```text
revoke old token
COMMIT

create replacement
COMMIT
```

That is incorrect.

Problems:

1. if replacement creation fails after revocation, user loses their valid refresh session
2. two concurrent refresh requests could both create replacement tokens

Use conditional DB update.

Correct flow:

```text
lookup session by token hash
→ validate expiry
→ conditional UPDATE where revoked_at IS NULL
→ inspect rowcount
→ only one refresh request wins
→ create replacement refresh session
→ commit revocation + replacement together
```

Conceptually:

```python
result = await db.execute(
    update(RefreshSession)
    .where(
        RefreshSession.id == session_id,
        RefreshSession.revoked_at.is_(None),
    )
    .values(
        revoked_at=datetime.now(timezone.utc)
    )
)

won_rotation = result.rowcount == 1
```

Do not commit inside this repository operation.

Then:

```python
if not won_rotation:
    await db.rollback()
    raise ValueError("Refresh token already used")
```

Create the replacement session in the same transaction.

Only then:

```python
await db.commit()
```

On failure:

```python
await db.rollback()
```

This design must be preserved.

---

# 32. LOGOUT

Logout should:

```text
hash refresh cookie
→ find session
→ revoke if still active
→ clear access cookie
→ clear refresh cookie
```

Logout should be idempotent.

Missing or already-invalid refresh tokens should not cause unnecessary crashes.

---

# 33. USER REPOSITORY

Expected methods:

```python
get_by_google_id(...)
get_by_id(...)
create(...)
```

Use:

```python
select(User)
```

No raw SQL.

---

# 34. REFRESH SESSION REPOSITORY

Expected conceptual methods:

```python
create(...)
get_by_token_hash(...)
revoke_if_active(...)
```

Be mindful of transaction ownership.

Do not force commits from repository methods that are part of multi-step refresh rotation.

---

# 35. ERROR HANDLING

Return `401 Unauthorized` for:

- missing access token
- invalid access token
- expired access token
- missing refresh token
- invalid refresh token
- expired refresh token
- revoked refresh token
- already-used refresh token

Do not expose sensitive internal implementation details.

Prefer project-specific exceptions if they already exist.

Otherwise service-level `ValueError` is acceptable and routes/dependencies can convert it to `HTTPException`.

---

# 36. FRONTEND AUTHENTICATION

Frontend uses:

- React
- TypeScript
- Vite
- Tailwind
- pnpm
- Google Identity Services

Google script:

```html
<script src="https://accounts.google.com/gsi/client" async defer></script>
```

Frontend `.env`:

```env
VITE_GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
```

Google button uses:

```ts
window.google.accounts.id.initialize({
    client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
    callback: handleCredentialResponse,
});
```

Send:

```ts
response.credential;
```

to:

```text
POST http://localhost:8000/auth/google
```

with:

```ts
credentials: "include";
```

Never store tokens in:

```text
localStorage
sessionStorage
React state
```

Tokens belong in HttpOnly cookies.

---

# 37. FRONTEND STYLING

Use Tailwind CSS.

Do not reintroduce a custom `login.css` architecture unless explicitly asked.

Preserve existing working Tailwind login UI.

---

# 38. AUDIO PROCESSING ARCHITECTURE

After auth is confirmed, build the transcription pipeline incrementally.

Do not start with Celery.

First make synchronous processing work.

Initial conceptual flow:

```text
POST /transcriptions
→ authenticate
→ accept UploadFile
→ validate
→ save original
→ create Transcription
→ process
→ transcribe
→ save result
→ return result
```

Only later:

```text
POST /transcriptions
→ create job
→ enqueue worker
→ return job id

worker
→ process
→ update DB
→ publish status
```

---

# 39. FIRST CORE FUNCTIONALITY AFTER AUTH

The first transcription feature must be only:

```text
authenticated upload
→ basic validation
→ save original file locally
→ create Transcription row
→ status = UPLOADED
→ return created job
```

Do not implement in the same task:

```text
FFprobe
FFmpeg
VAD
Groq
Celery
Redis
WebSockets
S3
```

Stop after this vertical slice works.

---

# 40. AUDIO UPLOAD

Use:

```python
UploadFile
```

Support both:

- file uploads
- browser MediaRecorder output

Both should use the same backend route.

Validate basic constraints first:

- allowed file types
- allowed extensions where useful
- max size

Later use FFprobe for actual media validation.

Do not trust MIME type alone.

---

# 41. STORAGE

Do not store raw audio in DB.

Start with local filesystem storage.

Create an abstraction only when useful.

Future implementation may target:

```text
S3
MinIO
other S3-compatible storage
```

DB stores:

```text
original_storage_key
```

not file bytes.

---

# 42. FFPROBE

Add FFprobe in its own task after upload works.

Use it to extract:

- actual media validity
- duration
- useful metadata

Store:

```text
duration_seconds
```

Reject non-audio or malformed files appropriately.

---

# 43. FFMPEG

Add FFmpeg normalization in a separate task.

Target format:

```text
mono
16 kHz
PCM WAV
```

Keep the pipeline simple.

Do not over-process clean audio.

---

# 44. SPEECH DETECTION

Add VAD only after normalized audio works.

Preferred:

```text
Silero VAD
```

Conceptual service:

```text
SpeechDetectionService
```

It should return speech windows / ranges.

---

# 45. STT PROVIDER ABSTRACTION

Do not hardcode Groq calls deep inside `TranscriptionService`.

Use a provider boundary.

Conceptually:

```python
class SpeechToTextProvider:
    async def transcribe(...):
        ...
```

Concrete:

```text
GroqProvider
```

Keep provider-specific API details isolated.

---

# 46. TRANSCRIPTION SERVICE

`TranscriptionService` should orchestrate the pipeline.

Conceptual flow:

```text
load job
→ mark PROCESSING
→ normalize audio
→ run VAD
→ call STT provider
→ assemble transcript
→ validate transcript
→ save result
→ mark COMPLETED
```

On handled failure:

```text
status = FAILED
error_message = sanitized message
```

Do not leave jobs stuck in `PROCESSING`.

---

# 47. PROCESSING TIME

Use monotonic timing:

```python
time.perf_counter()
```

Store milliseconds:

```text
processing_time_ms
```

---

# 48. TRANSCRIPT SEGMENTS

Store segments as JSONB.

Example:

```json
[
    {
        "start": 2.5,
        "end": 6.8,
        "text": "This is the transcript."
    }
]
```

Do not create a segment table unless there is a concrete query requirement.

---

# 49. DOWNLOAD / EXPORT

Implement later as its own task.

Potential formats:

```text
.txt
.json
.srt
.vtt
```

Do not build this during initial upload/transcription tasks.

---

# 50. WEBSOCKETS

Do not build WebSockets until synchronous processing works.

Later:

```text
worker updates DB
→ publish status
→ WebSocket forwards event
→ frontend updates UI
```

Database remains the source of truth.

WebSocket is only for live notifications.

---

# 51. CELERY / REDIS

Do not add Celery until the synchronous pipeline works.

Later:

```text
Redis = broker / messaging infrastructure
Celery = background worker
```

Long-running transcription should eventually leave the normal HTTP request lifecycle.

But synchronous-first is intentional.

---

# 52. REQUIREMENTS

The Python project may include:

```text
fastapi
uvicorn[standard]
python-multipart

pydantic
pydantic-settings
email-validator
python-dotenv

sqlalchemy
asyncpg
alembic

google-auth
requests
python-jose[cryptography]
cryptography

httpx

celery
redis

boto3

groq

pytest
pytest-asyncio
pytest-cov

ruff
```

Add VAD-specific Python dependencies only when that task begins.

Do not add:

```text
PostgreSQL
FFmpeg
FFprobe
Docker
Redis server
```

to requirements.txt because those are system/services, not Python libraries.

---

# 53. ALEMBIC

Alembic is configured async.

All ORM models must be imported so:

```python
Base.metadata
```

contains all tables before autogenerate.

Commands:

```bash
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

Do not bypass migrations for schema changes.

---

# 54. DOCKER

Current Docker Compose primarily runs PostgreSQL.

Do not unnecessarily Dockerize FastAPI yet.

Later Compose may include:

```text
postgres
redis
api
worker
minio
```

but only when those features are actually needed.

---

# 55. TESTING PHILOSOPHY

Test each vertical slice before continuing.

Do not postpone all testing until the end.

Examples:

Authentication:

```text
valid Google login
invalid Google login → 401
/auth/me works
/auth/me without cookie → 401
refresh works
old refresh token cannot be reused
two simultaneous refreshes → one wins
replacement failure → old session preserved through rollback
expired refresh token → 401
logout revokes session
logout clears cookies
```

Upload:

```text
authenticated upload succeeds
unauthenticated upload rejected
invalid type rejected
oversized file rejected
file stored
DB row created
status = UPLOADED
```

FFprobe:

```text
real audio accepted
invalid media rejected
duration extracted
```

FFmpeg:

```text
output is mono
output is 16kHz
output is PCM WAV
failure handled
```

STT:

```text
sample audio transcribes
provider error handled
empty transcript handled
```

---

# 56. REPORT FORMAT AFTER EVERY TASK

After completing the current task, stop.

Do not continue.

Return:

```text
Implemented:
<what was completed>

Files changed:
<files>

Tested:
<commands/tests and results>

Not implemented yet:
<next logical functionality>
```

Then wait for the developer.

---

# 57. IMPORTANT STYLE PREFERENCES

The developer wants to understand the system.

When working:

- explain the reason for architectural decisions briefly
- avoid huge unexplained rewrites
- preserve working code
- build in small increments
- do not introduce controllers
- do not bypass services
- use repositories for DB access
- use `db` consistently
- use SQLAlchemy 2.0 async syntax
- do not ask questions when repository inspection already answers them
- do not change conventions casually
- do not implement future functionality early

---

# 58. PLANNED IMPLEMENTATION ORDER

Unless explicitly reprioritized, work approximately in this order:

```text
1. Authentication completion / hardening

2. Protected audio upload
   → basic validation
   → save file
   → create UPLOADED transcription

3. FFprobe media validation
   → duration

4. FFmpeg normalization

5. VAD / speech detection

6. Groq provider integration

7. Transcript assembly

8. Quality validation

9. Complete synchronous transcription pipeline

10. Transcript download/export

11. Frontend transcription workflow

12. Celery + Redis

13. WebSocket status

14. production storage / S3-compatible storage

15. broader production hardening/tests
```

Do not implement step N+1 while working on step N unless step N genuinely cannot function without it.

---

# 59. IMMEDIATE INSTRUCTION

Start by inspecting the repository.

Do not make code changes immediately.

Inspect:

- backend structure
- frontend structure
- current auth routes
- AuthService
- token utilities
- RefreshSessionRepository
- UserRepository
- get_current_user dependency
- models
- migrations
- cookie configuration
- CORS configuration

Determine whether authentication is complete and correct.

Pay particular attention to:

- refresh-token rotation atomicity
- concurrent refresh safety
- transaction boundaries
- logout revocation
- cookie paths
- access-token validation
- service/repository separation

If authentication has issues, fix only authentication and stop.

If authentication is complete enough to proceed, the next task is only:

```text
Authenticated audio upload
→ basic validation
→ local file storage
→ create Transcription row
→ status UPLOADED
→ return job
```

Do not add FFprobe, FFmpeg, VAD, Groq, Celery, Redis, WebSockets, or S3 in that task.

After completing that one functionality, stop and wait for further instruction.
