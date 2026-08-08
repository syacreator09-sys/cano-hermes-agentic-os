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

<!-- AAH:START -->
## Adaptive Agent Harness
For AAH work use fresh independent producer/evaluator brains, sealed SPEC/RUBRIC contracts, persistent findings/evidence, and deterministic gates. External runs: `.aah/bin/factory run "<goal>" --profile auto`; native Claude Code: `/aah`. Never expose `.env` values, bypass Guardian, or treat another agent's conclusion as proof. MCP servers remain project/user managed and are selected only when required.
<!-- AAH:END -->
