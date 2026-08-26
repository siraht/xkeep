#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/x-ai-brief"
HERMES_SCRIPT_DIR="$HOME/.hermes/scripts"
HERMES_SCRIPT="$HERMES_SCRIPT_DIR/xkeep-brief.sh"
JOBS_FILE="$HOME/.hermes/cron/jobs.json"
GATEWAY_PID_FILE="$HOME/.hermes/gateway.pid"
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
PREVIOUS_TIMEZONE="$(hermes config get timezone 2>/dev/null || true)"
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

# The gateway caches timezone configuration. Restart the gateway recorded by
# Hermes itself; its supervisor brings it back without root access.
if [[ "$PREVIOUS_TIMEZONE" != "America/Denver" && -r "$GATEWAY_PID_FILE" ]]; then
  GATEWAY_PID="$(python3 - "$GATEWAY_PID_FILE" <<'PY'
import json, sys

try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("pid", ""))
except (OSError, ValueError):
    pass
PY
)"
  if [[ "$GATEWAY_PID" =~ ^[1-9][0-9]*$ ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill -TERM "$GATEWAY_PID"
    for _ in {1..30}; do
      NEW_PID="$(python3 - "$GATEWAY_PID_FILE" <<'PY'
import json, sys

try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("pid", ""))
except (OSError, ValueError):
    pass
PY
)"
      if [[ "$NEW_PID" =~ ^[1-9][0-9]*$ && "$NEW_PID" != "$GATEWAY_PID" ]] && kill -0 "$NEW_PID" 2>/dev/null; then
        break
      fi
      sleep 1
    done
  fi
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
