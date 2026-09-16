# Backend

Run Docker commands from the repository root. The root `Dockerfile` contains
`backend` and `web` targets; root Compose files start the full application.

See [project setup](../README.md) for local commands and
[AWS deployment](../deploy/README.md) for EC2 installation, HTTPS, and updates.

For Python development, run `uv sync --locked` here after starting `dev-db`
through the root Compose file. Configure `.env`, then run
`uv run alembic upgrade head` and `uv run uvicorn app.main:app --reload`.
