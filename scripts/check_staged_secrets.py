#!/usr/bin/env python3
"""K12 (plan HERMES-KICKOFF, Seguridad v2) -- pre-commit secret scan.

Same idea F16 (Plan Prometeo) already ran by hand over Prometeo's own
diffs before closing that phase: grep the *staged* diff (not the whole
tree -- a pre-existing secret already committed elsewhere is a separate,
bigger problem this hook isn't trying to solve) for patterns that look
like a real long-lived credential, and refuse the commit if it finds one.

Deliberately simple, not a vendored third-party secret-scanning tool: a
handful of high-confidence regexes for the provider families this repo
actually integrates with (see `~/.env`/`cano_hermes/config.py`/
`subprocess_executor.py`'s `EXECUTOR_SECRET_ALLOWLIST`), plus one generic
catch-all for a long assigned-looking token. False negatives are expected
and accepted (this is a last-resort net, not the only line of defense --
see SECURITY.md's "Secretos" section for the real policy: secrets never
belong in Git, full stop); false positives are handled with an inline
`# pragma: allowlist secret` escape hatch rather than a giant exception
list that rots.

Usage: run with no arguments, invoked by `.pre-commit-config.yaml`'s local
hook (or directly: `python3 scripts/check_staged_secrets.py`). Exits 1 and
prints every offending `file:line` with the matched pattern's name when it
finds something; exits 0 (silent) otherwise.
"""

from __future__ import annotations

import re
import subprocess
import sys

# (name, compiled pattern) -- ordered roughly by specificity so the first
# match reported for a line is usually the most useful one.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("anthropic-api-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("openai-api-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("telegram-bot-token", re.compile(r"\b\d{6,10}:[A-Za-z0-9_-]{30,}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "generic-long-secret-assignment",
        re.compile(
            r"""(?i)\b(api[_-]?key|secret|token|password|passwd|access[_-]?key)\b
                \s*[:=]\s*
                ['"]?[A-Za-z0-9_\-/+]{24,}['"]?""",
            re.VERBOSE,
        ),
    ),
]

ALLOWLIST_MARKER = "pragma: allowlist secret"

# Files whose whole purpose is to document the *shape* of a secret, never a
# real one -- checked by path suffix, not content, so a genuine leak in one
# of these still gets caught if it doesn't otherwise look like a template.
PATH_ALLOWLIST_SUFFIXES = (
    "scripts/check_staged_secrets.py",  # this file's own patterns/docstring
    ".env.example",
    ".env.sample",
)


def _staged_diff() -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--no-color"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        # `git diff` itself failing (not "found differences") -- don't
        # silently pass a commit we couldn't actually scan.
        sys.stderr.write(f"check_staged_secrets: 'git diff --cached' failed: {result.stderr}\n")
        sys.exit(2)
    return result.stdout


def _scan(diff_text: str) -> list[str]:
    findings: list[str] = []
    current_file = "?"
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[len("+++ b/") :]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if any(current_file.endswith(suffix) for suffix in PATH_ALLOWLIST_SUFFIXES):
            continue
        content = line[1:]
        if ALLOWLIST_MARKER in content:
            continue
        for name, pattern in PATTERNS:
            match = pattern.search(content)
            if match:
                findings.append(f"{current_file}: possible {name} -- {match.group(0)[:12]}...")
                break  # one report per line is enough
    return findings


def main() -> int:
    diff_text = _staged_diff()
    findings = _scan(diff_text)
    if not findings:
        return 0
    sys.stderr.write("check_staged_secrets: refusing commit, possible secret(s) staged:\n")
    for finding in findings:
        sys.stderr.write(f"  {finding}\n")
    sys.stderr.write(
        "\nIf this is a false positive, add `# pragma: allowlist secret` on the same line.\n"
        "If it's real: unstage it, rotate the credential if it was ever committed before, "
        "and move it to .env / a secrets manager (see SECURITY.md).\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
