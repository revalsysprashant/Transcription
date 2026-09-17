# Audio Transcription

Record or upload audio, sign in with Google, and get a transcript using Groq Whisper.
Download transcripts as TXT, SRT, or VTT. The default upload limits are **25 MB**
and **60 minutes** per recording.

## Start here

This guide runs the complete app on your computer with Docker. Docker installs
Python, Node, FFmpeg, PostgreSQL, and the app dependencies inside containers.
You do not need to install those separately.

Use a **Bash terminal on Linux, macOS, or Windows WSL**. Commands below run in the
same terminal, from the repository root unless a step says otherwise. Paste only
the contents of code blocks. Finish each step before continuing.

Already have the app working? Jump to [daily commands](#daily-commands).
Updating the AWS website? Follow [the deployment guide](deploy/README.md).

## 1. Check Docker and get the code

You need Git, Docker with Docker Compose, and OpenSSL. Check them:

```bash
git --version
docker --version
docker compose version
openssl version
```

Each command should print a version. If Docker is missing, install Docker Desktop
on macOS/Windows, or Docker Engine with the Compose plugin on Linux. Start Docker
Desktop before continuing if you use it.

If you **already have this repository**, enter its folder. On the original computer:

```bash
cd /home/yg/Transcription
```

On another computer, clone it once:

```bash
git clone https://github.com/revalsysprashant/Transcription.git
cd Transcription
```

Confirm you are in the correct folder and Docker is running:

```bash
ls Dockerfile compose.yml
docker info
```

If Docker reports a permission error on Linux, fix your Docker installation's user
permissions before continuing. Avoid switching between `sudo docker` and ordinary
`docker` throughout this guide.

## 2. Get the two account settings

You need these before the app can sign in and transcribe:

| Setting | Where it comes from | What to copy |
| --- | --- | --- |
| Google client ID | Google Cloud Console → Google Auth Platform → Clients | A **Web application** client ID ending in `.apps.googleusercontent.com` |
| Groq API key | Groq Console → API Keys | A newly created API key |

In your Google web client, add this exact **Authorized JavaScript origin**:

```text
http://localhost:8080
```

Use no trailing slash. This app does not need a redirect URI. If your Google app
is in testing mode, add your sign-in email as a test user when required by your
Google project configuration. A Google **client secret** is not used by this app.

## 3. Create the local settings once

The next block asks for your client ID and API key, generates random secrets, and
creates `backend/.env` and `.env.docker`. The API key is hidden while you type.
It refuses to overwrite either existing file.

```bash
(
  set -eu
  umask 077
  if [ -e backend/.env ] || [ -e .env.docker ]; then
    echo 'Settings already exist. Keep them; use the editing instructions below.'
    exit 1
  fi
  read -r -p 'Paste Google client ID: ' setup_google_id
  read -r -s -p 'Paste Groq API key (hidden): ' setup_groq_key
  printf '\n'
  test -n "$setup_google_id" && test -n "$setup_groq_key"
  setup_db_password=$(openssl rand -hex 32)
  setup_jwt_secret=$(openssl rand -hex 48)
  set -C
  printf '%s\n' \
    "GOOGLE_CLIENT_ID=$setup_google_id" \
    "GROQ_API_KEY=$setup_groq_key" \
    "JWT_SECRET=$setup_jwt_secret" \
    'MAX_AUDIO_SIZE_MB=25' \
    'MAX_AUDIO_DURATION_SECONDS=3600' > backend/.env
  printf '%s\n' \
    "POSTGRES_PASSWORD=$setup_db_password" \
    "GOOGLE_CLIENT_ID=$setup_google_id" > .env.docker
  echo 'Created backend/.env and .env.docker.'
)
```

**If settings already exist:** keep them and edit them in your text editor.
`backend/.env` needs `GOOGLE_CLIENT_ID`, `GROQ_API_KEY`, and `JWT_SECRET`.
`.env.docker` needs `POSTGRES_PASSWORD` and the same `GOOGLE_CLIENT_ID`.
Do not change an existing database password simply to rerun setup: PostgreSQL
retains the password established when its volume was first created.

For a partially completed setup, create only the missing file using these field
names. Generate any missing random password or JWT secret with `openssl rand -hex 32`.
Never paste real credentials into GitHub, screenshots, or chat.

Compose supplies the container's database URL automatically. This Docker setup
does not require `frontend/.env` or a locally installed Python environment.

## 4. Build and start the app

```bash
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up -d --build --wait
docker compose --env-file .env.docker ps
curl --fail http://localhost:8080/health
```

The first command succeeds silently. The first build can take several minutes
while downloading dependencies. The last command should print:

```json
{"status":"ok"}
```

Open **http://localhost:8080** in your browser. Sign in with Google, select a short
recording, and click **Upload and transcribe**. Microphone recording works on
localhost and HTTPS. Successful health checks alone do not test Google or Groq;
complete one real transcription to verify both.

## Daily commands

Run these from the repository root.

**Start the existing app:**

```bash
docker compose --env-file .env.docker up -d --wait
```

**Apply code or environment changes:**

```bash
docker compose --env-file .env.docker up -d --build --wait
```

**See errors:**

```bash
docker compose --env-file .env.docker logs --tail=100 backend web db
```

**Stop while keeping recordings and database data:**

```bash
docker compose --env-file .env.docker down
```

Do not add `-v`: that deletes the named storage volumes. Volumes survive container
replacement, but are not backups.

## Push changes to GitHub

```bash
git remote -v
git status
git add -A
git diff --cached --stat
git diff --cached
git commit -m "Describe your changes"
SSH_ASKPASS_REQUIRE=never git push -u origin main
```

Review the staged changes before committing. If there is nothing to commit,
skip the commit and push. If SSH asks for a passphrase, use the passphrase chosen
when creating your SSH key. HTTPS remotes use GitHub authentication instead.

The root `.gitignore` excludes environment files, keys, dependencies, local audio,
comparison output, and deployment archives. Sanitized `.env.example` templates
are allowed. `.gitignore` does not remove files already tracked or in old commits.
If GitHub blocks a secret, remove it from every affected commit and rotate it;
do not bypass protection for a real credential. Coordinate history changes if
other people already use the affected branch.

**Pushing to GitHub does not update the AWS website.** Automatic deployment is
not configured. Use [manual deployment instructions](deploy/README.md).

## Common problems

| What you see | What to do |
| --- | --- |
| `no configuration file provided` | Enter the repository folder containing `compose.yml`. |
| `Set POSTGRES_PASSWORD` or `Set GOOGLE_CLIENT_ID` | Complete step 3 and include `--env-file .env.docker` in Compose commands. |
| Cannot connect to Docker | Start Docker Desktop or the Docker service, then rerun `docker info`. |
| Port 8080 already in use | Stop the other application using that port. |
| Database password authentication failed | Restore the password used when this database volume was created. Editing the file alone does not change PostgreSQL's password. |
| Google sign-in fails | Check the exact origin `http://localhost:8080` and matching client IDs in both environment files, then rebuild. |
| Provider/transcription error | Check `GROQ_API_KEY` and the backend logs. Recreate the backend after changing its environment. |
| Upload rejected | Use a file no larger than 25 MB and no longer than 60 minutes. |
| No speech detected | Try a short recording with clear speech. |
| Build/start fails | Read the first error, then run the logs command above. Do not delete volumes as a troubleshooting shortcut. |

## How the app works

Open [app-flow.excalidraw](app-flow.excalidraw) in Excalidraw for the single editable
app diagram.

```text
Browser → Caddy → FastAPI → FFprobe / FFmpeg → Silero → Groq Whisper
                       → PostgreSQL transcript + original audio volume
```

The backend normalizes audio, detects speech, groups clips with padding and
overlap, and combines results using original timestamps. When detected speech
covers less than 60% of a recording and the normalized WAV is at most 20 MB, it
uses the full audio instead. No detected speech produces an empty transcript
without a Groq request. Temporary processing files are removed after the request.

`Dockerfile` builds the backend and frontend images. `compose.yml` runs the local
stack; `compose.production.yml` runs the public HTTPS stack. Their databases and
audio volumes are separate.

## Optional: development without app containers

This is a separate workflow for developers who need hot reload. Use the Docker
steps above if you simply want to run the app. This workflow requires Python
3.12+, uv, Node.js 24, pnpm 11.22.0, FFmpeg/FFprobe, and Docker on your computer.

With `.env.docker` configured, start only the development database:

```bash
docker compose --env-file .env.docker --profile development up -d --wait dev-db
```

In `backend/.env`, keep your Google/Groq/JWT settings and set:

```dotenv
DATABASE_URL=postgresql+asyncpg://transcription:transcription@localhost:5433/transcription_db
APP_ENV=development
DEBUG=true
COOKIE_SECURE=false
```

Create `frontend/.env` with your actual client ID:

```dotenv
VITE_GOOGLE_CLIENT_ID=REPLACE_WITH_YOUR_CLIENT_ID.apps.googleusercontent.com
```

Also add `http://localhost:5173` to Google's Authorized JavaScript origins.
In a terminal from the repository root:

```bash
cd backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Keep that terminal running. In another terminal from the repository root:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open **http://localhost:5173**. This uses a separate development database on port
5433; it does not copy data from the Docker app or AWS.

## Optional: run tests

After installing the development dependencies above, from the repository root:

```bash
(cd backend && uv run python -m pytest -q)
(cd frontend && pnpm build && node --test tests/*.test.mjs)
```
