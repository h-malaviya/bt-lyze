# Interview Evaluation Platform

Self-hosted interview recording, transcription, and candidate evaluation platform. The application
uses Supabase for authentication and PostgreSQL, Deepgram for diarized transcription, Claude for
structured evaluation, Redis/ARQ for background jobs, and either Supabase Storage or Azure Blob
Storage for recordings.

## Prerequisites

- Docker Desktop with Docker Compose v2
- A Supabase project with Database, Auth, and Storage enabled
- A Deepgram API key
- A Claude Code OAuth token
- Python 3.11 or 3.12 and `uv` for provisioning and local development
- Node.js 22 and npm for local frontend development
- FFmpeg on `PATH` when running the worker outside Docker

Azure Blob Storage and ngrok are optional.

## 1. Configure the environment

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Set these required values in `.env`:

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Browser-safe Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only Supabase service key |
| `DATABASE_URL` | Supabase PostgreSQL connection string with SSL enabled |
| `VITE_SUPABASE_URL` | Same project URL compiled into the frontend |
| `VITE_SUPABASE_ANON_KEY` | Same anonymous key compiled into the frontend |
| `DEEPGRAM_API_KEY` | Deepgram transcription credential |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Agent SDK authentication token |

Keep `.env`, service-role keys, database credentials, OAuth tokens, and Azure credentials out of
Git. Only variables beginning with `VITE_` are exposed to the browser.

## 2. Provision Supabase

Install the Python environment and apply the database schema, storage buckets, triggers, indexes,
and row-level security policies:

```powershell
uv sync --dev
uv run python scripts/provision_database.py --apply
```

Running the command again is safe and verifies the resulting configuration.

### Create a panel account

Create a user under **Supabase Dashboard → Authentication → Users**, copy its UUID, and then run:

```powershell
uv run python scripts/provision_panel.py --user-id <user-uuid> --name "Panel 1"
```

The command creates or links the panel and assigns the required `role` and `panel_id` application
metadata. Sign out and back in after changing metadata so Supabase issues a refreshed JWT.

### Create an administrator

Create the user in Supabase Auth and assign this application metadata through the Supabase Admin
API or dashboard:

```json
{"role":"admin"}
```

The administrator must sign in again after the metadata is updated.

## 3. Choose recording storage

### Supabase Storage

Supabase is the default:

```dotenv
RECORDING_STORAGE_PROVIDER=supabase
```

The database provisioning command creates private `recordings` and `transcripts` buckets and their
access policies.

### Azure Blob Storage

Set `RECORDING_STORAGE_PROVIDER=azure`, create a private container, and configure the matching
`AZURE_STORAGE_*` values in `.env`. Prefer managed identity or a service principal with **Storage
Blob Data Contributor**. Use `AZURE_STORAGE_CONNECTION_STRING` only as a development fallback.

Browser uploads require a Blob service CORS rule for each exact frontend origin:

- Allowed methods: `PUT`, `OPTIONS`
- Allowed headers: `content-type`, `x-ms-blob-type`
- Exposed headers: `x-ms-request-id`, `x-ms-version`
- Max age: `3600` seconds

For example:

```powershell
az storage account blob-service-properties cors-rule add `
  --resource-group "<resource-group>" `
  --account-name "<storage-account>" `
  --allowed-origins "http://localhost:8080" `
  --allowed-methods PUT OPTIONS `
  --allowed-headers content-type x-ms-blob-type `
  --exposed-headers x-ms-request-id x-ms-version `
  --max-age 3600
```

Add deployed or ngrok origins explicitly instead of using `*`.

## 4. Run with Docker Compose

Start the web application, API, worker, and Redis:

```powershell
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080). The API health endpoint is available at
[http://localhost:8080/api/health](http://localhost:8080/api/health), and development API docs are
available at [http://localhost:8080/api/docs](http://localhost:8080/api/docs).

For file watching during development:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build --watch
```

### Optional ngrok tunnel

Set `NGROK_AUTHTOKEN`, then run:

```powershell
docker compose --profile tunnel up --build
```

View the assigned URL at [http://localhost:4040](http://localhost:4040). Add that exact HTTPS origin
to `ALLOWED_ORIGINS` and, when using Azure, to the Blob service CORS rule. Rebuild the frontend when
its `VITE_` variables change.

## 5. Run services directly

Start Redis through Docker:

```powershell
docker compose up -d redis
```

Install dependencies:

```powershell
uv sync --dev
Set-Location web
npm ci
Set-Location ..
```

Run each service in a separate terminal from the repository root:

```powershell
uv run uvicorn api.app.main:app --reload --port 8000
```

```powershell
uv run arq worker.settings.WorkerSettings --custom-log-dict worker.settings.ARQ_LOG_CONFIG
```

```powershell
Set-Location web
$env:API_PROXY_TARGET="http://localhost:8000"
npm run dev
```

The Vite frontend runs at [http://localhost:5173](http://localhost:5173).

## Verification

Check configured external services:

```powershell
uv run python scripts/verify_integrations.py
```

Run a non-database Deepgram and Claude smoke test:

```powershell
uv run python scripts/smoke_pipeline.py
```

Run the project checks:

```powershell
uv run ruff check api worker scripts
uv run pytest
Set-Location web
npm run lint
npm test -- --runInBand
npm run build
```

The worker loads its prompt and credentials at startup. Restart the worker after changing the
evaluation prompt, model, or related environment values.
