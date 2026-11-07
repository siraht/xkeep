#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$1" == "chat" ]]
shift
QUERY_FILE=""
while (($#)); do
  if [[ "$1" == "--query-file" ]]; then
    QUERY_FILE="$2"
    shift 2
  else
    shift
  fi
done

[[ -s "$QUERY_FILE" ]]
grep -Fq '<untrusted-feed-json>' "$QUERY_FILE"
grep -Fq '## Other interesting items' "$QUERY_FILE"
grep -Fq 'strong bias toward inclusion' "$QUERY_FILE"
grep -Fq 'one story per paragraph' "$QUERY_FILE"
grep -Fq 'Do not mention skipped' "$QUERY_FILE"
grep -Fq 'Interesting or surprising items are welcome' "$QUERY_FILE"

cat <<'EOF'
# X AI Brief — test

## Tools, models, and releases

**Agent runtime v2 released.** The release adds deterministic task replay and structured logs. https://x.com/dev/status/2
EOF
