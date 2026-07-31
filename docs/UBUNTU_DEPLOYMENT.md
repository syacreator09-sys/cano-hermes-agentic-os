# Ubuntu deployment

Recommended target: Ubuntu 24.04 bare metal on the dedicated i5 with XFCE for optional GUI. Hermes runs under systemd; untrusted workers run in rootless containers. Claude Code and Codex are installed on the host and invoked programmatically with isolated Git worktrees. Do not expose Docker socket to agents.
