# Architecture

1. GitHub sends pull request webhooks to FastAPI.
2. `github.webhook.verify_signature` validates the `X-Hub-Signature-256` HMAC.
3. `ReviewService` fetches changed files with a GitHub App installation token.
4. Tree-sitter builds AST summaries for supported source files.
5. Semgrep scans fetched file contents for security signals.
6. OpenAI receives only PR metadata, patch excerpts, AST summaries, and Semgrep evidence.
7. Findings are converted to GitHub review comments using `path`, `line`, and `side=RIGHT`.


## Reliability controls

- Webhook deliveries are claimed in SQLite by `X-GitHub-Delivery` before work is queued.
- Finding fingerprints are persisted to avoid repeat comments for the same PR issue.
- GitHub API calls use installation-token caching, API version headers, pagination for PR files, and retry/backoff for transient failures.
- Semgrep and Tree-sitter failures are isolated so one analysis stage cannot fabricate findings or crash every review.
- Findings are normalized against changed diff lines before inline comments are created.
