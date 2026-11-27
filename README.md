# Multiverse

> Observe every reality your code can become.

Multiverse is open-source behavioural infrastructure for self-hosted Flagsmith. It discovers how feature configurations change an application, preserves proven configurations as versioned realities, carries signed user intent between compatible products, and resolves the permitted experience at runtime.

## Table of contents

- [Why Multiverse](#why-multiverse)
- [Product model](#product-model)
- [Capabilities](#capabilities)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Configuration and credentials](#configuration-and-credentials)
- [Product workflow](#product-workflow)
- [API](#api)
- [Development and testing](#development-and-testing)
- [Security](#security)
- [Operations](#operations)
- [Project status](#project-status)
- [License](#license)

## Why Multiverse

Feature flags create many possible products inside one codebase. Conventional dashboards describe configuration; they do not prove what a user can observe. Multiverse creates an evidence chain:

1. **Observe** real workflows across valid configurations.
2. **Version** behaviours worth reviewing or keeping.
3. **Carry** approved preferences as signed portable intent.
4. **Resolve** intent against application policy and live Flagsmith state.

Behavioural equivalence is observational. It remains scoped to an application build, workflow version, and captured evidence.

## Product model

### Atlas — observe

Atlas generates exhaustive, pairwise, or adaptive configurations, executes structured Playwright workflows, normalizes observations, and builds an evidence-backed behaviour graph.

### Verse — version

Verse turns observed configurations into immutable SHA-256 commits. Teams can branch, inspect behavioural diffs, perform three-way merges, and issue expiring previews without another deployment.

### Passport — carry

Passport implements the Semantic Feature Interchange Protocol (SFIP). Ed25519-signed profiles carry semantic preferences—not raw flag authority. Applications accept only capabilities declared by their manifests and permitted by policy.

### Runtime — resolve

Runtime combines identity, entitlements, Passport traits, preview state, application policy, and live Flagsmith evaluation in a deterministic precedence order with provenance.

## Capabilities

- Authorized application registry with SSRF protection
- Self-hosted Flagsmith connection and snapshot synchronization
- Structured workflow registration and isolated worker execution
- Exhaustive, pairwise, and adaptive exploration
- Behavioural fingerprints, evidence, and similarity graphs
- Immutable commits, branches, diffs, merges, and previews
- Passport issue, verification, import, export, rotation, and revocation
- Manifest-driven semantic capability translation
- Runtime resolution and sanitized SDK observations
- Workspace isolation and cookie-based authentication
- Responsive product workspaces for every dashboard module

## Architecture

```text
Browser / SDK
  ├── React + Vite dashboard (5173)
  │     ├── Applications
  │     ├── Atlas
  │     ├── Verse
  │     ├── Passports
  │     └── Runtime
  └── FastAPI control plane (8001)
        ├── MySQL
        ├── Redis / RQ
        ├── Playwright exploration worker
        ├── Ed25519 signing service
        └── self-hosted Flagsmith (8000)
              └── PostgreSQL
```

| Layer | Technology |
|---|---|
| Web | React, TypeScript, Vite, Tailwind CSS, GSAP, Motion |
| API | FastAPI, Pydantic, SQLAlchemy |
| Data | MySQL, Redis, PostgreSQL for Flagsmith |
| Exploration | Playwright and RQ |
| Feature evaluation | Self-hosted Flagsmith |
| Signing | Ed25519 and JWKS |
| Orchestration | Docker Compose |

## Quick start

Prerequisites: Docker Desktop, Node.js 20+, and Python 3.12 for local API development.

```powershell
Copy-Item .env.example .env
python scripts/generate_secrets.py
docker compose up --build -d
```

Open:

- Web: `http://localhost:5173`
- API: `http://localhost:8001`
- OpenAPI: `http://localhost:8001/docs`
- Flagsmith: `http://localhost:8000`

```powershell
Invoke-RestMethod http://localhost:8001/health
Invoke-RestMethod http://localhost:8001/ready
docker compose ps
```

## Configuration and credentials

Copy `.env.example` to `.env`, then generate encryption, JWT, and Passport signing material:

```powershell
python scripts/generate_secrets.py
```

For Flagsmith:

1. Open `http://localhost:8000` and create the first administrator.
2. Create an organisation, project, and non-production environment.
3. Generate a Management API token and environment key.
4. Add the required values to `.env`.
5. Restart `api` and `worker`.

See [CREDENTIALS.md](CREDENTIALS.md) for every variable and where to obtain it. Never commit `.env`, private keys, Management API tokens, or environment keys.

## Product workflow

1. Create an account and workspace.
2. Register an application you own or may test.
3. Connect a non-production Flagsmith environment.
4. Declare the semantic capability manifest.
5. Register a structured workflow.
6. Run an **Atlas** exploration and inspect evidence.
7. Create a **Verse** branch from a proven configuration.
8. Issue signed preferences through **Passport**.
9. Submit a **Runtime** resolution and inspect provenance.

Production environments cannot be mutated by Atlas. Exploration targets must match their registered base URL.

## API

| Area | Routes |
|---|---|
| Authentication | `/api/v1/auth/*` |
| Applications | `/api/v1/apps/*` |
| Atlas | `/api/v1/explorations`, `/api/v1/behaviours/*` |
| Verse | `/api/v1/branches`, `/api/v1/merge/*`, `/api/v1/shares` |
| Passport | `/api/v1/passports/*`, `/.well-known/jwks.json` |
| Runtime | `/api/v1/runtime/resolve`, `/api/v1/runtime/observations` |
| Operations | `/health`, `/ready`, `/api/v1/system/status`, `/api/v1/metrics` |

Use `http://localhost:8001/docs` for current request and response schemas.

## Development and testing

```powershell
npm install
npm run dev

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services\api\requirements.txt
.\.venv\Scripts\python.exe scripts\generate_secrets.py
.\.venv\Scripts\python.exe -m uvicorn services.api.main:app --reload --port 8001
```

Verification:

```powershell
npm run lint
npm run build
.\.venv\Scripts\python.exe -m pytest -q
```

The suite covers authentication, Atlas generation and fingerprints, Verse diff and merge behaviour, and Passport signing and tamper rejection.

## Security

- Flagsmith credentials remain server-side and encrypted at rest.
- Registered base URLs constrain exploration scope.
- Production environment mutation is rejected.
- Workflows use a structured action schema; arbitrary API-side scripts are rejected.
- Preview tokens expire and are stored as SHA-256 hashes.
- Passports are Ed25519-signed and revocable.
- Passports cannot grant undeclared or policy-forbidden capabilities.
- Runtime observations redact common secret fields.
- Workspace membership scopes access to application data.

Before public deployment, rotate development secrets and configure TLS, secure cookies, trusted origins, backups, and external secret management.

## Operations

- Atlas needs a connected sandbox and registered workflow.
- Redis powers queued exploration; worker readiness appears in the dashboard.
- Flagsmith and Multiverse use separate databases.
- Use pairwise or adaptive exploration with explicit budgets for large domains.
- Behavioural equivalence is evidence scoped, never universal.

## Project status

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), [FULL_AUDIT.md](FULL_AUDIT.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

Multiverse is distributed under the terms in [LICENSE](LICENSE).
