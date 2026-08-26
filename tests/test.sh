#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
export OPENCLAW_STATE_DIR="$TMP/openclaw"
mkdir -p "$HOME/.config/x-ai-brief" "$TMP/bin"
ln -s "$ROOT/tests/fake_xbird.py" "$TMP/bin/xbird"
export PATH="$TMP/bin:$PATH"
cp "$ROOT/config.example.json" "$HOME/.config/x-ai-brief/config.json"

FIRST="$TMP/first.json"
python3 "$ROOT/scripts/x_feed.py" prepare >"$FIRST"
python3 - "$FIRST" <<'PY'
import json, sys
p=json.load(open(sys.argv[1]))
assert p['counts']['forYouFetched']==2
assert p['counts']['followingFetched']==2
assert p['counts']['uniqueUnseenForAgent']==3
assert p['items'][1]['sources']==['forYou','following']
print(p['runId'])
PY
RUN_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["runId"])' "$FIRST")"
python3 "$ROOT/scripts/x_feed.py" prepare >"$TMP/reused.json"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["reusedPending"] is True' "$TMP/reused.json"
python3 "$ROOT/scripts/x_feed.py" commit "$RUN_ID" >"$TMP/commit.json"
python3 "$ROOT/scripts/x_feed.py" prepare --fresh >"$TMP/second.json"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["counts"]["uniqueUnseenForAgent"] == 0' "$TMP/second.json"
python3 "$ROOT/scripts/x_feed.py" status >"$TMP/status.json"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["seenCount"] == 3' "$TMP/status.json"
python3 -m py_compile "$ROOT/scripts/x_feed.py"
echo "all tests passed"
bash -n "$ROOT/install.sh"
bash -n "$ROOT/run-codex.sh"
bash -n "$ROOT/install-codex-timer.sh"
