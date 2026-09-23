# v79 Engineering Plan

## Objective

v79 will improve operational reliability and release observability without expanding the Live Money boundary.

## Priorities

### 1. Immutable build identity

Expose the deployed Git commit and release identifier through runtime metadata so operators can prove which source revision is running without relying on image history.

Acceptance criteria:

- application image receives commit and release build arguments;
- `/api/system` reports the release and full Git SHA;
- deployment verification compares runtime SHA with GitHub `main`;
- tests reject missing or malformed production build identity.

### 2. Production-safe deployment tooling

Add a repository-owned deployment script that validates required configuration, preserves the current application image, updates only the app service, and performs rollback automatically if health checks fail.

Acceptance criteria:

- no shell-sourcing of Compose environment files;
- database, Redis and broker services are never recreated by an app-only deployment;
- bounded health-check retries;
- explicit rollback command and audit output;
- shell static analysis and documented dry-run procedure.

### 3. Release evidence endpoint

Extend release readiness reporting with build identity, migration revision, dependency health and certified provider scope.

Acceptance criteria:

- read-only ADMIN-visible evidence;
- no secrets or credential material returned;
- simulation certification cannot imply Live readiness;
- regression coverage for every safety boundary.

### 4. Operational documentation consistency

Remove ambiguous ports, endpoint names and obsolete deployment examples from active documentation.

Acceptance criteria:

- Oracle production port and health endpoint are consistent across active docs;
- environment-file handling is accurate;
- deployment and rollback procedures have one canonical source;
- superseded instructions are explicitly marked historical.

### 5. Dependency maintenance

Resolve the existing Starlette TestClient and AnyIO deprecation warnings through compatible dependency upgrades and test adjustments.

Acceptance criteria:

- full suite passes without the two known deprecation warnings;
- FastAPI/Starlette/httpx compatibility is pinned and documented;
- no authentication, session or API behavior regression.

## Non-goals

- enabling Live Money;
- increasing order-size limits;
- bypassing provider certification;
- replacing PostgreSQL, Redis or broker bridges;
- unrelated frontend redesign.

## Delivery sequence

`DESIGN → BUILD → TEST → REVIEW → ORACLE ISOLATED VALIDATION → MERGE → APP-ONLY DEPLOY → HEALTH/CERTIFICATION CHECK → DOCUMENT`
