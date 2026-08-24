# PR Guardian V1

PR Guardian V1 is a production-ready FastAPI service for GitHub App pull request reviews. It verifies GitHub webhook signatures, fetches PR file evidence, parses AST structure with Tree-sitter, runs Semgrep security checks, asks OpenAI for evidence-first review findings, and posts line-anchored review comments back to the pull request.

## Features

- FastAPI backend with `/healthz` and `/webhooks/github` endpoints.
- GitHub App authentication using installation tokens.
- HMAC SHA-256 webhook verification.
- Tree-sitter AST summaries for common languages.
- Semgrep security scanning via the Semgrep CLI and `p/security-audit`.
- OpenAI JSON review generation constrained to supplied evidence.
- GitHub pull request review comments anchored to changed lines.
- Docker, Docker Compose, GitHub Actions CI, and Railway deployment config.

## Quick start

```bash
cp .env.example .env
# Fill in GitHub App, webhook, and OpenAI values.
docker compose up --build
```

The service listens on `http://localhost:8000` and exposes `GET /healthz`. The Docker image installs the Semgrep CLI separately from application dependencies so CI and local tests stay fast and deterministic.

## GitHub App setup

1. Create a GitHub App with these permissions:
   - Pull requests: Read & write
   - Contents: Read-only
   - Metadata: Read-only
2. Subscribe to Pull request events.
3. Set the webhook URL to `https://<your-domain>/webhooks/github`.
4. Generate a private key and copy it into `PR_GUARDIAN_GITHUB_PRIVATE_KEY` with escaped newlines.
5. Configure the webhook secret as `PR_GUARDIAN_GITHUB_WEBHOOK_SECRET`.
6. Install the app on repositories you want reviewed.

## Configuration

All configuration uses the `PR_GUARDIAN_` prefix.

| Variable | Description |
| --- | --- |
| `GITHUB_APP_ID` | GitHub App ID. |
| `GITHUB_PRIVATE_KEY` | PEM private key, with newlines escaped as `\n`. |
| `GITHUB_WEBHOOK_SECRET` | Shared webhook secret for HMAC verification. |
| `OPENAI_API_KEY` | API key used by the review engine. |
| `OPENAI_MODEL` | Review model, default `gpt-4.1-mini`. |
| `MAX_FILES_PER_REVIEW` | Review file cap, default `20`. |
| `MAX_PATCH_CHARS` | Patch excerpt cap per file, default `12000`. |
| `POST_REVIEW_COMMENTS` | Set false for dry-run behavior. |

Semgrep is expected on `PATH` at runtime. If the binary is missing, PR Guardian records a non-fatal warning and still runs the OpenAI review over patch and AST evidence.

## Local development

```bash
./scripts/setup.sh
source .venv/bin/activate
pytest
./scripts/run.sh
```

## Railway deployment

1. Create a Railway project from this repository.
2. Add the environment variables from `.env.example`.
3. Railway uses `railway.toml` and the Dockerfile automatically.
4. Point the GitHub App webhook URL at `https://<railway-domain>/webhooks/github`.

## Security model

PR Guardian rejects unsigned or incorrectly signed webhook requests before parsing payloads. It uses GitHub installation tokens scoped to the installed repository and instructs the OpenAI reviewer to emit only evidence-backed findings from patches, AST summaries, and Semgrep results.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
