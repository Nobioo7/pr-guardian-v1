# Deployment

## Docker

Build and run locally:

```bash
docker compose up --build
```

## Railway

Railway builds from `Dockerfile` through `railway.toml`. Configure all required `PR_GUARDIAN_*` variables in the Railway dashboard and use `/healthz` as the health check path.


## Semgrep runtime

The application treats Semgrep as an external CLI. The provided Dockerfile installs it with `pipx`; non-Docker deployments should install `semgrep` on `PATH` before enabling production reviews.
