# Deployment

## Docker

Build and run locally:

```bash
docker compose up --build
```

## Railway

Railway builds from `Dockerfile` through `railway.toml`. Configure all required `PR_GUARDIAN_*` variables in the Railway dashboard and use `/healthz` as the health check path.
