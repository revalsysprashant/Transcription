# AWS Docker deployment

The app has been deployed on Ubuntu EC2 using an uploaded source archive.
Local edits and GitHub pushes do not update that deployment automatically.
There is currently no GitHub Actions deployment workflow.
All Docker commands run from the repository root. One root `Dockerfile` builds
the backend and web targets. Local development uses `compose.yml`; production
uses `compose.production.yml`. No Dockerfile or Compose file is needed in backend/.
Production creates a separate, initially empty database and audio volume. It does
not transfer existing users or recordings from your computer.

## Update the existing AWS website

Use this section if the server is already running. You do not need to create a
new server, database, or environment file for each code change.

**On your computer**, open a Bash terminal in the repository root. The prompts
let you supply the server details without editing the commands:

```bash
read -r -p 'Server public IP (current server: 65.2.211.225): ' deploy_server
read -r -p 'Full SSH key path (example: /home/yg/.ssh/transcription-aws.pem): ' deploy_key
chmod 600 "$deploy_key"
bash deploy/package.sh
scp -i "$deploy_key" deploy/transcription.tar.gz "ubuntu@$deploy_server:~/transcription/"
ssh -i "$deploy_key" "ubuntu@$deploy_server"
```

Enter actual values at both prompts; the examples are not automatic defaults.
The AWS SSH key is separate from your GitHub SSH key. If SSH times out, check
that the server security group permits port 22 from your current public IP.
If packaging or uploading fails, stop and fix that error before connecting.

You are now **on the server**. Paste:

```bash
cd ~/transcription
tar -xzf transcription.tar.gz
sudo docker compose --env-file .env.production -f compose.production.yml config --quiet
sudo docker compose --env-file .env.production -f compose.production.yml up -d --build --wait
sudo docker compose --env-file .env.production -f compose.production.yml ps
curl --fail https://transcribe.65-2-211-225.sslip.io/health
```

The health check should print `{"status":"ok"}`. If you change the hostname, use
the new hostname in that command. Open the website and test sign-in and a real
transcription. Leave the server terminal with:

```bash
exit
```

The archive excludes secrets. Keep the server's existing `.env.production` and
persistent volumes. Extraction does not delete old files: if your change removes
or renames source files, review those obsolete files on the server before rebuilding.

If startup fails, run this **on the server** and inspect the error:

```bash
cd ~/transcription
sudo docker compose --env-file .env.production -f compose.production.yml logs --tail=100 backend web db
```

Do not run `down -v` or regenerate database credentials to fix an update error.
There may be a short interruption while containers are replaced; this setup does
not provide zero-downtime deployment or automatic rollback.

## First deployment to a new server

The remaining setup sections apply to a **new server**. Skip them for ordinary
updates to the existing website. Run local commands from the repository root.

## Production configuration

- Frontend and API share one HTTPS origin. Refresh cookies retain their `/auth` path.
- Caddy obtains and renews certificates and redirects HTTP to HTTPS.
- Backend cookies are Secure and HttpOnly; debug SQL logging is disabled.
- Only Caddy publishes ports. PostgreSQL and the API stay inside Docker's network.
- Database, recordings, and certificates use persistent volumes. Logs rotate.
- Backend starts only after PostgreSQL is healthy and applies database migrations.
- `.env.production` contains fresh database/JWT secrets and your existing Google/Groq
  settings. It is excluded from version control and the transfer archive.

## 1. Configure the hostname

Edit `.env.production` locally and set `DOMAIN='transcribe.your-domain.com'`.
Use a hostname only, without a URL scheme, port, or path. Keep the other secrets.
If the file already exists, keep it. For a first deployment, create it using this
Bash block on your computer. It generates separate production database and JWT
secrets and asks for the account settings; no local Python installation is needed:

```bash
(
  set -eu
  umask 077
  if [ -e .env.production ]; then
    echo '.env.production already exists; keeping it unchanged.'
    exit 1
  fi
  read -r -p 'Public hostname, without https://: ' setup_domain
  read -r -p 'Google web client ID: ' setup_google_id
  read -r -s -p 'Groq API key (hidden): ' setup_groq_key
  printf '\n'
  test -n "$setup_domain" && test -n "$setup_google_id" && test -n "$setup_groq_key"
  setup_db_password=$(openssl rand -hex 32)
  setup_jwt_secret=$(openssl rand -hex 48)
  set -C
  printf '%s\n' \
    "DOMAIN=$setup_domain" \
    "POSTGRES_PASSWORD=$setup_db_password" \
    "JWT_SECRET=$setup_jwt_secret" \
    "GOOGLE_CLIENT_ID=$setup_google_id" \
    "GROQ_API_KEY=$setup_groq_key" > .env.production
  echo 'Created .env.production.'
)
```

Keep this file out of Git. Do not use this block to rotate one setting on an
existing deployment; edit only that setting instead.

In Google Cloud → Google Auth Platform → Clients → your web client, add
`https://transcribe.your-domain.com` under Authorized JavaScript origins.
Keep the localhost origins for development. This login implementation does not
need a redirect URI. Use the exact HTTPS origin for your deployment.

## 2. AWS configuration for a new server

Create an Ubuntu 24.04 x86-64 EC2 instance; 2 vCPUs and 4 GB RAM are a starting
estimate, not a measured capacity guarantee. Allow enough disk for container
images and saved recordings (start around 30 GB and monitor usage).
Use a stable public address and point the hostname's DNS A record to it. Do not
add an AAAA record unless IPv6 is configured on the server.

Security group inbound rules:

| Port | Protocol | Source |
| --- | --- | --- |
| 22 | TCP | Your current public IP only |
| 80 | TCP | Internet |
| 443 | TCP | Internet |
| 443 | UDP | Internet, optional HTTP/3 |

Do not open 5432 or 8000. Outbound connectivity is needed for image downloads,
Google authentication, Groq transcription, and certificate issuance.

## 3. Package and copy from your computer

Replace `KEY.pem`, `SERVER_IP`, and the example hostname with your values.

```bash
bash deploy/package.sh
ssh -i KEY.pem ubuntu@SERVER_IP 'mkdir -p ~/transcription && chmod 700 ~/transcription'
scp -i KEY.pem deploy/transcription.tar.gz .env.production ubuntu@SERVER_IP:~/transcription/
ssh -i KEY.pem ubuntu@SERVER_IP
```

## 4. Install and start on the server

```bash
cd ~/transcription
chmod 600 .env.production
tar -xzf transcription.tar.gz
sudo bash deploy/install-docker-ubuntu.sh
sudo docker compose --env-file .env.production -f compose.production.yml config --quiet
sudo docker compose --env-file .env.production -f compose.production.yml up -d --build --wait
sudo docker compose --env-file .env.production -f compose.production.yml ps
curl --fail https://transcribe.your-domain.com/health
```

Expect `{"status":"ok"}`. Certificate issuance requires working DNS and publicly
reachable ports 80/443. Open the HTTPS site, sign in, record and transcribe a clip,
then test reopening the job and downloading the original. Health checks alone
do not verify Google login, Groq credentials, or a complete transcription.

## Logs and updates

```bash
sudo docker compose --env-file .env.production -f compose.production.yml logs --tail=100 backend web
```

For updates, run this on your computer from the repository root, replacing
`KEY.pem` and `SERVER_IP`:

```bash
bash deploy/package.sh
scp -i KEY.pem deploy/transcription.tar.gz ubuntu@SERVER_IP:~/transcription/
ssh -i KEY.pem ubuntu@SERVER_IP
```

Then run on the server:

```bash
cd ~/transcription
tar -xzf transcription.tar.gz
sudo docker compose --env-file .env.production -f compose.production.yml up -d --build --wait
sudo docker compose --env-file .env.production -f compose.production.yml ps
curl --fail https://transcribe.your-domain.com/health
```

Use your actual hostname in the health check. Archive extraction overwrites
included files but does not delete files removed from the source; review removed
or renamed application files during an update. Use `deploy/package.sh` rather
than archiving the whole working directory, which could include secrets.
Routine code updates do not require uploading the environment file again.
Keep the same `.env.production` and Compose project name so volumes and credentials
remain consistent. Do not run `down -v`: it deletes the persistent volumes.
Back up both PostgreSQL and the audio volume before schema-changing updates;
Docker volumes survive container replacement but are not off-server backups.

## Rotate the Groq API key

1. Create a replacement API key in your Groq account. Keep it out of Git and chat.
2. Edit `GROQ_API_KEY` in local `backend/.env` and `.env.production` where used.
3. On EC2, edit the same setting in `~/transcription/.env.production`, preserving
   the existing database password, JWT secret, domain, and other settings.
4. From `~/transcription`, recreate the backend to load the changed environment:

   ```bash
   chmod 600 .env.production
   sudo docker compose --env-file .env.production -f compose.production.yml up -d --no-deps --force-recreate --wait backend
   ```

5. Restart any local backend using the old key. Test an actual transcription
   locally and in production; `/health` does not validate the Groq key.
6. Revoke the old key in Groq after verifying the replacement. Revoke it immediately
   if there is evidence of misuse.

Removing a credential from Git history does not rotate it. Rotation must be
completed separately. Do not regenerate the entire production environment file
on an existing deployment merely to replace the Groq key.

## Stop and restart

Run these commands from `~/transcription` on EC2:

```bash
sudo docker compose --env-file .env.production -f compose.production.yml restart
sudo docker compose --env-file .env.production -f compose.production.yml down
sudo docker compose --env-file .env.production -f compose.production.yml up -d --build --wait
```

`down` retains the database and audio volumes; `down -v` deletes them.

## Sources

- AWS security group rules: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html
- Docker Ubuntu installation: https://docs.docker.com/engine/install/ubuntu/
- Caddy HTTPS prerequisites: https://caddyserver.com/docs/automatic-https
