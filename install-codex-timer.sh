#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/x-ai-brief"
UNIT_DIR="$HOME/.config/systemd/user"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex is not on PATH. Install/authenticate Codex CLI before enabling this timer." >&2
  exit 1
fi

rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")" "$UNIT_DIR"
cp -a "$SOURCE" "$DEST"

cat > "$UNIT_DIR/x-ai-brief.service" <<EOF
[Unit]
Description=Generate an AI briefing from the authenticated X feed
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=PATH=%h/.local/bin:%h/.cargo/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/bin/bash %h/.local/share/x-ai-brief/run-codex.sh
EOF

cat > "$UNIT_DIR/x-ai-brief.timer" <<'EOF'
[Unit]
Description=Generate X AI briefs three times daily

[Timer]
OnCalendar=*-*-* 08:00:00 America/Denver
OnCalendar=*-*-* 13:00:00 America/Denver
OnCalendar=*-*-* 18:00:00 America/Denver
Persistent=true
RandomizedDelaySec=60
Unit=x-ai-brief.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now x-ai-brief.timer

echo "Codex fallback installed."
echo "Run now: systemctl --user start x-ai-brief.service"
echo "Check schedule: systemctl --user list-timers x-ai-brief.timer"
echo "Read briefs: $HOME/Documents/X AI Briefs/latest.md"
