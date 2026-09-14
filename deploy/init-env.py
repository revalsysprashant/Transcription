"""Create production secrets once; requires the backend's python-dotenv."""
import os
from pathlib import Path
import secrets

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
source = dotenv_values(root / "backend/.env")
for key in ("GOOGLE_CLIENT_ID", "GROQ_API_KEY"):
    if not source.get(key):
        raise SystemExit(f"Set {key} in backend/.env first")
values = {
    "DOMAIN": "",
    "POSTGRES_PASSWORD": secrets.token_hex(32),
    "JWT_SECRET": secrets.token_hex(48),
    "GOOGLE_CLIENT_ID": source["GOOGLE_CLIENT_ID"],
    "GROQ_API_KEY": source["GROQ_API_KEY"],
}
target = root / ".env.production"
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(".env.production already exists; kept existing secrets unchanged.")
with os.fdopen(fd, "w") as output:
    output.write("# Set DOMAIN to your hostname, without https:// or a path.\n")
    for key, value in values.items():
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        output.write(f"{key}='{escaped}'\n")
print("Created .env.production with private permissions. Set DOMAIN before deploying.")
