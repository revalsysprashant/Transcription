# AWS-ready Docker deployment

The production configuration is prepared, but no AWS resources have been created.
All Docker commands run from the repository root. One root `Dockerfile` builds
the backend and web targets. Local development uses `compose.yml`; production
uses `compose.production.yml`. No Dockerfile or Compose file is needed in backend/.
Production creates a separate, initially empty database and audio volume. It does
not transfer existing users or recordings from your computer.

## Prepared locally

- Frontend and API share one HTTPS origin. Refresh cookies retain their `/auth` path.
- Caddy obtains and renews certificates and redirects HTTP to HTTPS.
- Backend cookies are Secure and HttpOnly; debug SQL logging is disabled.
- Only Caddy publishes ports. PostgreSQL and the API stay inside Docker's network.
- Database, recordings, and certificates use persistent volumes. Logs rotate.
- Backend starts only after PostgreSQL is healthy and applies database migrations.
- `.env.production` contains fresh database/JWT secrets and your existing Google/Groq
  settings. It is excluded from version control and the transfer archive.

## 1. Choose the future hostname

Edit `.env.production` locally and set `DOMAIN='transcribe.your-domain.com'`.
Use a hostname only, without a URL scheme, port, or path. Keep the other secrets.
If the file is missing, generate it once from the project root:

```bash
backend/.venv/bin/python deploy/init-env.py
```

In Google Cloud → Google Auth Platform → Clients → your web client, add
`https://transcribe.your-domain.com` under Authorized JavaScript origins.
Keep the localhost origins for development. This login implementation does not
need a redirect URI. These steps need your actual hostname and remain pending.

## 2. Future AWS configuration

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

## 4. Install and start on the future server

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

For updates, copy and extract a new archive, then rerun `up -d --build --wait`.
Keep the same `.env.production` and Compose project name so volumes and credentials
remain consistent. Do not run `down -v`: it deletes the persistent volumes.
Back up both PostgreSQL and the audio volume before schema-changing updates;
Docker volumes survive container replacement but are not off-server backups.

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
