#!/usr/bin/env bash
# Generates ./.env (gitignored, compose-local -- used ONLY for ${VAR}
# substitution in docker-compose.yml, never mounted/copied into a
# container) from the vault, copying values through without ever printing
# them to stdout/stderr.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

VAULT="$HOME/.secrets/credenciales/credenciales/.env"
OUT=".env"
NAMES=(KIMI_API_KEY KIMI_BASE_URL NVIDIA_NIM_API_KEY RAPIDAPI_KEY APIFY_API_KEY BASEROW_CONTENT_TOKEN)

: > "$OUT"
chmod 600 "$OUT"
for name in "${NAMES[@]}"; do
    line="$(grep -m1 "^${name}=" "$VAULT" || true)"
    if [ -n "$line" ]; then
        echo "$line" >> "$OUT"
    fi
done
echo "Wrote $(wc -l < "$OUT") of ${#NAMES[@]} candidate vars to $OUT (values not printed)."
