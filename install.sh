#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
XBIRD_REV="dfc5040ea0c5f4885ed3102ba282a8188d170278"
XBIRD_SOURCE="git+https://github.com/reorx/xbird.git@${XBIRD_REV}"
STATE_ROOT="${OPENCLAW_STATE_DIR:-$HOME/.openclaw}"
MANAGED_SKILL_DIR="$STATE_ROOT/skills/x-ai-brief"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/x-ai-brief"
CONFIG_FILE="$CONFIG_DIR/config.json"
DO_SCHEDULE=1
DO_STAGE=1
OPENCLAW_AVAILABLE=0
CODEX_FALLBACK_INSTALLED=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [--no-schedule] [--no-stage]

Installs xbird when needed, installs x-ai-brief as a shared OpenClaw skill,
creates a default configuration, verifies X authentication, stages the first
feed snapshot, and attempts to schedule briefs for 08:00, 13:00, and 18:00
America/Denver using the main session's last delivery route.
EOF
}

while (($#)); do
  case "$1" in
    --no-schedule) DO_SCHEDULE=0 ;;
    --no-stage) DO_STAGE=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

say() { printf '\n==> %s\n' "$*"; }
warn() { printf '\nWARNING: %s\n' "$*" >&2; }

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! command -v xbird >/dev/null 2>&1 && ! command -v bird >/dev/null 2>&1; then
  say "Installing the pinned Linux-compatible xbird client"
  if command -v uv >/dev/null 2>&1; then
    uv tool install "$XBIRD_SOURCE"
    # uv may have installed into ~/.local/bin before that directory entered this shell's PATH.
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  else
    cat >&2 <<EOF
Neither xbird/Bird nor uv is installed.
Install uv from Astral's official installer, then rerun this script:
  curl -LsSf https://astral.sh/uv/install.sh | sh
  exec \$SHELL -l
  ./install.sh
EOF
    exit 1
  fi
fi

XCLI=""
if command -v xbird >/dev/null 2>&1; then
  XCLI="$(command -v xbird)"
elif command -v bird >/dev/null 2>&1; then
  XCLI="$(command -v bird)"
else
  echo "X client installation completed but xbird is not on PATH. Run: uv tool update-shell" >&2
  exit 1
fi

say "Installing the shared OpenClaw skill"
if command -v openclaw >/dev/null 2>&1; then
  OPENCLAW_AVAILABLE=1
  if ! openclaw skills install "$ROOT" --global --as x-ai-brief --force; then
    warn "OpenClaw's local installer failed; copying the skill into the managed skill directory instead."
    rm -rf "$MANAGED_SKILL_DIR"
    mkdir -p "$(dirname "$MANAGED_SKILL_DIR")"
    cp -a "$ROOT" "$MANAGED_SKILL_DIR"
  fi
else
  warn "openclaw is not on PATH. The skill will be copied into $MANAGED_SKILL_DIR, but OpenClaw itself still needs to be installed/configured."
  rm -rf "$MANAGED_SKILL_DIR"
  mkdir -p "$(dirname "$MANAGED_SKILL_DIR")"
  cp -a "$ROOT" "$MANAGED_SKILL_DIR"
fi

mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_FILE" ]]; then
  cp "$ROOT/config.example.json" "$CONFIG_FILE"
  say "Created $CONFIG_FILE"
else
  say "Preserved existing $CONFIG_FILE"
fi

# Resolve the actual installed path in case OpenClaw chose it.
if [[ -f "$MANAGED_SKILL_DIR/scripts/x_feed.py" ]]; then
  INSTALLED="$MANAGED_SKILL_DIR"
else
  INSTALLED="$ROOT"
fi

say "Checking authenticated X access with $(basename "$XCLI")"
AUTH_OK=0
if "$XCLI" check && "$XCLI" whoami; then
  AUTH_OK=1
else
  warn "No working authenticated browser session was found. Log into x.com in Chrome/Chromium or Firefox on this machine, then run: $XCLI check && $XCLI whoami"
fi

if ((AUTH_OK && DO_STAGE)); then
  say "Staging the first personalized feed snapshot"
  SNAPSHOT="$(mktemp)"
  if python3 "$INSTALLED/scripts/x_feed.py" prepare >"$SNAPSHOT"; then
    python3 - "$SNAPSHOT" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding='utf-8'))
c = p['counts']
print(f"Prepared run {p['runId']}: {c['uniqueUnseenForAgent']} unseen items from "
      f"{c['forYouFetched']} For You and {c['followingFetched']} Following results.")
print("The first /x-ai-brief invocation will reuse this staged snapshot.")
PY
  else
    warn "Authentication worked, but the initial home-feed fetch failed. Run xbird query-ids --fresh (or bird query-ids --fresh), then retry /x-ai-brief."
  fi
  rm -f "$SNAPSHOT"
fi

if ((DO_SCHEDULE && OPENCLAW_AVAILABLE)); then
  say "Scheduling three daily briefs in America/Denver"
  if openclaw cron list 2>/dev/null | grep -Fq "X AI brief"; then
    echo "An X AI brief cron job already exists; leaving it unchanged."
  else
    PROMPT='Use the x-ai-brief skill now. Review every staged unseen feed item, return the concise English briefing, and commit only after the briefing is fully drafted.'
    if ! openclaw cron create "0 8,13,18 * * *" "$PROMPT" \
      --name "X AI brief" \
      --session main \
      --tz "America/Denver" \
      --announce \
      --channel last; then
      warn "The cron job could not be created or its last delivery route was unavailable. The skill is installed; from the OpenClaw chat where you want delivery, ask: Schedule x-ai-brief for 8:00 AM, 1:00 PM, and 6:00 PM America/Denver and deliver it in this chat."
    fi
  fi
fi

if ((!OPENCLAW_AVAILABLE)) && command -v codex >/dev/null 2>&1; then
  say "OpenClaw is absent; installing the direct Codex fallback and user timer"
  "$ROOT/install-codex-timer.sh"
  CODEX_FALLBACK_INSTALLED=1
fi

say "Installed"
if ((OPENCLAW_AVAILABLE)); then
  echo "Run it immediately from OpenClaw with: /x-ai-brief"
elif ((CODEX_FALLBACK_INSTALLED)); then
  echo "Run it immediately with: systemctl --user start x-ai-brief.service"
  echo "Read the result at: $HOME/Documents/X AI Briefs/latest.md"
else
  echo "Neither OpenClaw nor Codex CLI was found; the collector is installed, but an agent engine still needs to be connected."
fi
echo "Collector status: python3 '$INSTALLED/scripts/x_feed.py' status"
echo "Configuration: $CONFIG_FILE"
echo "This integration only reads X; it never posts, likes, follows, or bookmarks."
