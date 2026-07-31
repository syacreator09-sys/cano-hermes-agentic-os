# Architecture

Cano Hermes OS is separated into three planes:

1. **Control plane:** Conductor, Task Engine, Registry, Policy, Budget, Approvals and Evaluations.
2. **Execution plane:** Claude Code, Codex, Hermes Agent, OpenClaw, browser and Python workers.
3. **Intelligence plane:** subscription-first routing plus DeepSeek, Qwen, Kimi, Grok, Anthropic and OpenAI APIs.

The Conductor receives compact context and never performs specialist work. Each execution uses a task contract, workspace, permissions, budget, timeout and acceptance gates. Factory V5 and Command Center remain external integrations.
