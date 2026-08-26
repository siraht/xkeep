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
grep -Fq '## New tools, models, and releases' "$QUERY_FILE"
grep -Fq 'Open-source AI tools' "$QUERY_FILE"

cat <<'EOF'
# X AI Brief — test

## Must know

Agent runtime v2 was released. https://x.com/dev/status/2

Coverage: reviewed 3 unseen items from 2 For You and 2 Following results. Selected 1 story.
EOF
