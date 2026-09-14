# Audio Transcription

Record audio in your browser or upload a file, transcribe speech with Groq Whisper,
and save the original recording and transcript. Sign in with Google to access your
own saved jobs and export transcripts as TXT, SRT, or VTT.

## How it works

```text
React frontend → FastAPI → FFprobe validation → FFmpeg normalization
                        → Silero speech detection → Groq Whisper
                        → PostgreSQL transcript + original audio on disk
```

The backend converts audio to mono 16 kHz PCM WAV, detects speech, transcribes
speech clips, and maps timestamps back to the original recording. Processing runs
during the upload request; there is no background queue or WebSocket job stream.
Temporary processing files are removed after the request.

Default limits are **25 MB** and **60 minutes** per recording. Microphone recording
requires localhost or HTTPS. Transcription requires an internet connection and a
working Groq API key.

## Architecture diagrams and function guide

Explore the [architecture atlas](docs/architecture/README.md) for the complete
application flow, eight visual diagrams, and explanations of all 85 named functions.

- [Open the offline visual atlas](docs/architecture/index.html)
- [Editable Excalidraw board](docs/architecture/app-flow.excalidraw)
- [Mermaid diagrams](docs/architecture/diagrams.md)
- [Function-by-function reference](docs/architecture/function-reference.md)

## Local Docker setup

Run commands from the project root. You need Docker Engine with Docker Compose,
a Google OAuth web client, and a Groq API key. Python, Node, FFmpeg, and the speech
model dependencies are installed inside the images.

### 1. Configure the backend

If `backend/.env` does not already exist, copy the example:

```bash
cp -n backend/.env.example backend/.env
```

Edit `backend/.env` and set `GOOGLE_CLIENT_ID`, `GROQ_API_KEY`, and a long random
`JWT_SECRET`. Docker overrides `DATABASE_URL`, debug mode, cookie security, and
audio storage for its own environment. Keep credentials out of version control.

### 2. Configure Docker

If `.env.docker` already exists, keep it. Otherwise create it:

```bash
(umask 077; set -C; cat > .env.docker <<'ENV'
POSTGRES_PASSWORD=REPLACE_WITH_A_RANDOM_HEX_PASSWORD
GOOGLE_CLIENT_ID=REPLACE_WITH_YOUR_GOOGLE_CLIENT_ID
ENV
)
```

Replace both placeholders. Use the same Google client ID as `backend/.env`.
Generate random secrets with `openssl rand -hex 32`; use separate values for the
JWT secret and database password. Use a hexadecimal database password so it is
safe to embed in the database URL.

### 3. Configure Google sign-in

In Google Cloud Console, select your project, then open **Google Auth Platform →
Clients → your Web application client**. Add this Authorized JavaScript origin:

```text
http://localhost:8080
```

Keep `http://localhost:5173` too if you use the Vite development server. This app
uses Google's credential callback; it does not require an OAuth redirect URI.

### 4. Build and start

```bash
docker compose --env-file .env.docker up -d --build --wait
docker compose --env-file .env.docker ps
curl --fail http://localhost:8080/health
```

Open **http://localhost:8080**. The first build downloads the speech-processing
dependencies. PostgreSQL starts first, then the backend applies Alembic migrations,
and Caddy serves the frontend and proxies API requests on the same origin.
The health endpoint should return `{"status":"ok"}`.

Sign in, record a short clip, stop recording, then click **Upload and transcribe**.
The **Selected: recording-…** line identifies the recording even when the separate
file picker says **No file chosen**. Keep the returned job ID to reopen it later.

### Logs, updates, and stopping

```bash
# View recent errors
docker compose --env-file .env.docker logs --tail=100 backend web

# Rebuild after code changes
docker compose --env-file .env.docker up -d --build --wait

# Stop containers while preserving data
docker compose --env-file .env.docker down
```

Database and audio data live in named Docker volumes. Do not add `-v` to `down`
unless you intend to delete them. Keep your database password unchanged after
initialization; editing the environment file does not rotate an existing database
password. Volumes are persistent storage, not backups.

## Local development without app containers

You need Python 3.12+, uv, Node.js compatible with the frontend dependencies,
pnpm, and FFmpeg/FFprobe on your PATH. The backend lockfile selects CPU builds for
the speech-processing libraries.

Start the development PostgreSQL container:

```bash
docker compose -f backend/compose.yml up -d
```

Set this development database URL in `backend/.env`, along with your Google/Groq
credentials and JWT secret:

```dotenv
DATABASE_URL=postgresql+asyncpg://transcription:transcription@localhost:5433/transcription_db
```

Start the backend in one terminal:

```bash
cd backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Set `VITE_GOOGLE_CLIENT_ID` in `frontend/.env` to the same Google client ID. Then,
in another terminal:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open **http://localhost:5173**. Development API requests default to
`http://localhost:8000`; `VITE_API_URL` can override that address. Docker builds set
it to an empty string so requests use the website's own origin.

The development database, local Docker database, and production database are
separate. Switching between them does not migrate existing users or recordings.

## Production / AWS preparation

Production configuration is ready for a single Ubuntu server. No AWS resources
have been created by this setup. See **[the deployment guide](deploy/README.md)**
for server installation, DNS, firewall rules, Google sign-in, HTTPS, transfer, and
startup commands.

| File | Purpose |
| --- | --- |
| [compose.yml](compose.yml) | Local Docker stack at localhost:8080 |
| [compose.production.yml](compose.production.yml) | Public HTTPS stack with secure cookies and private API/database ports |
| [deploy/Caddyfile](deploy/Caddyfile) | HTTPS, certificate renewal, frontend serving, and API proxy |
| [deploy/install-docker-ubuntu.sh](deploy/install-docker-ubuntu.sh) | Docker and Compose installer for the future Ubuntu server |
| [deploy/init-env.py](deploy/init-env.py) | Creates production secrets without overwriting an existing file |
| [deploy/package.sh](deploy/package.sh) | Creates a transfer archive without secrets or recordings |

If `.env.production` is missing, generate it once after installing backend
dependencies with `uv sync --locked`:

```bash
backend/.venv/bin/python deploy/init-env.py
```

Set `DOMAIN` in `.env.production` to your actual hostname, without `https://` or a
path. The script reuses your Google/Groq settings and creates fresh database and
JWT secrets. Keep this file private and transfer it separately over SSH.

Validate the production configuration and create the transfer archive:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
bash deploy/package.sh
```

The archive is written to `deploy/transcription.tar.gz`. Production creates fresh
storage volumes. HTTPS issuance and public Google login remain unverified until
DNS points to a server and the public origin is registered with Google.

## Checks

Run backend tests from `backend/` after `uv sync --locked`:

```bash
uv run python -m pytest -q
```

Run frontend checks from `frontend/` after installing dependencies:

```bash
pnpm build
node --test tests/*.test.mjs
```

Both Docker images built successfully during deployment preparation. Production
Compose and Caddy configuration validation passed, the local HTTP health endpoint
responded successfully, and all 67 backend tests passed. These checks do not
replace testing Google login and a real transcription on the deployed hostname.

## Troubleshooting

- **Failed to fetch:** check backend health and logs. In development, start the API
  on port 8000. In Docker, use localhost:8080 and check the Caddy/backend services.
- **Google sign-in fails:** verify matching frontend/backend client IDs and the
  exact Authorized JavaScript origin, including scheme and port. Rebuild the
  frontend image after changing its client ID.
- **Transcription provider error:** check the Groq API key and provider availability;
  inspect backend logs for the failing request.
- **No speech detected:** try a clear recording and check microphone input. Recording
  and playback happen locally, while transcription needs the backend and Groq.
- **HTTPS unavailable:** check the production hostname, DNS, and inbound ports
  80/443. Follow the deployment guide before exposing the production stack.
