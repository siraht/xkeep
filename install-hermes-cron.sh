#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/x-ai-brief"
HERMES_SCRIPT_DIR="$HOME/.hermes/scripts"
HERMES_SCRIPT="$HERMES_SCRIPT_DIR/xkeep-brief.sh"
JOBS_FILE="$HOME/.hermes/cron/jobs.json"
JOB_NAME="X AI brief"

if ! command -v hermes >/dev/null 2>&1; then
  echo "hermes is not on PATH. Install and authenticate Hermes first." >&2
  exit 1
fi

install -d -m 755 "$DEST/scripts" "$HERMES_SCRIPT_DIR"
install -m 700 "$SOURCE/run-hermes.sh" "$DEST/run-hermes.sh"
install -m 755 "$SOURCE/scripts/x_feed.py" "$DEST/scripts/x_feed.py"
install -m 600 "$SOURCE/interests.md" "$DEST/interests.md"
install -m 644 "$SOURCE/config.example.json" "$DEST/config.example.json"

cat >"$HERMES_SCRIPT" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
export XKEEP_HERMES_SESSION=xkeep-brief
export XKEEP_PRINT_BRIEF=1
export XKEEP_NOTIFY=0
exec "$HOME/.local/share/x-ai-brief/run-hermes.sh"
EOF
chmod 700 "$HERMES_SCRIPT"

# Hermes evaluates cron expressions in its configured IANA timezone.
hermes config set timezone America/Denver >/dev/null

EXISTING_JOB="$(python3 - "$JOBS_FILE" "$JOB_NAME" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
name = sys.argv[2]
if path.exists():
    payload = json.loads(path.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", payload) if isinstance(payload, dict) else payload
    if isinstance(jobs, list):
        for job in jobs:
            if isinstance(job, dict) and job.get("name") == name:
                print(job.get("id", ""))
                break
PY
)"

if [[ -n "$EXISTING_JOB" ]]; then
  hermes cron edit "$EXISTING_JOB" \
    --schedule "0 8,13,18 * * *" \
    --name "$JOB_NAME" \
    --deliver telegram \
    --script xkeep-brief.sh \
    --no-agent >/dev/null
  hermes cron resume "$EXISTING_JOB" >/dev/null 2>&1 || true
  JOB_ID="$EXISTING_JOB"
else
  CREATE_OUTPUT="$(hermes cron create "0 8,13,18 * * *" \
    --name "$JOB_NAME" \
    --deliver telegram \
    --script xkeep-brief.sh \
    --no-agent)"
  printf '%s\n' "$CREATE_OUTPUT"
  JOB_ID="$(python3 - "$JOBS_FILE" "$JOB_NAME" <<'PY'
import json, sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
jobs = payload.get("jobs", payload) if isinstance(payload, dict) else payload
for job in jobs:
    if isinstance(job, dict) and job.get("name") == sys.argv[2]:
        print(job["id"])
        break
PY
)"
fi

# The Hermes gateway caches timezone configuration; restart it so the job's
# first calculated fire and every later DST transition use America/Denver.
if systemctl is-active --quiet hermes-gateway.service; then
  systemctl restart hermes-gateway.service
fi

# Prevent duplicate briefs from the legacy scheduler while preserving its
# unit files for users who intentionally switch back.
systemctl --user disable --now x-ai-brief.timer >/dev/null 2>&1 || true

echo "Hermes cron owns the schedule."
echo "Job: $JOB_NAME ($JOB_ID)"
echo "Schedule: 08:00, 13:00, and 18:00 America/Denver"
echo "Delivery: Telegram home chat"
echo "Session: xkeep-brief"
echo "Run now: hermes cron run $JOB_ID"
echo "History: hermes cron runs $JOB_ID"
