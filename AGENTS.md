# Agent Operating Contract

The Conductor delegates; it does not become a universal worker.

Every agent manifest declares:

- identity and team;
- objective and output contract;
- allowed tools and paths;
- preferred and fallback model profiles;
- budgets and timeouts;
- evaluation gates;
- lifecycle status.

Lifecycle:

`draft -> candidate -> quarantine -> testing -> approved -> active -> stale -> archived`

Agents must not receive Docker socket access, global secrets, unrestricted filesystem access or production permissions.
