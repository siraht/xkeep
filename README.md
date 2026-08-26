# xkeep

`xkeep` replaces X scrolling with an agent-reviewed briefing generated from the authenticated account's real **For You** and **Following** timelines. Its installed OpenClaw skill and service retain the `x-ai-brief` name for compatibility with the original bundle.

It uses `xbird` when available, falls back to Peter Steinberger's `bird`, sends every unseen item from a bounded snapshot to the model, preserves the feed's ranking positions, and commits deduplication state only after the briefing has been drafted. It never invokes an X write action.

## Install on Ubuntu / Omarchy

```bash
unzip x-ai-brief.zip
cd x-ai-brief
./install.sh
```

The installer prefers the current Linux-compatible `reorx/xbird` client and pins the audited revision included in `install.sh`. If `uv` is absent, install it from Astral's official installer and rerun the script.

Then invoke this in OpenClaw:

```text
/x-ai-brief
```

The installer also attempts to schedule delivery at **08:00, 13:00, and 18:00 America/Denver** through the main OpenClaw session's last chat route. If that route is not resolvable, ask from the desired OpenClaw chat:

```text
Schedule x-ai-brief for 8:00 AM, 1:00 PM, and 6:00 PM America/Denver and deliver it in this chat.
```

When OpenClaw is absent, the installer prefers the locally installed Hermes CLI and creates a systemd user timer. Customize [interests.md](interests.md) before installing, or edit `~/.local/share/x-ai-brief/interests.md` afterward.

## Authentication

`xbird` reads the existing logged-in X browser session. On Linux, Chrome/Chromium is the most reliable source; Firefox is also supported.

```bash
xbird check
xbird whoami
xbird home -n 20 --json | python3 -m json.tool
```

If X changes a GraphQL query ID:

```bash
xbird query-ids --fresh
```

You may instead supply `AUTH_TOKEN` and `CT0` through the process environment. When the browser is on another machine, run `./configure-x-auth.sh` on the machine hosting xkeep and paste only those two X cookie values into its hidden prompts. They are saved to `~/.config/x-ai-brief/credentials.env` with mode `600`; they are loaded only for feed collection and removed from the Hermes process environment.

## What “the feed” means

X does not expose a finite canonical For You stream. Each call produces a ranked, personalized snapshot that may change between requests. The default run asks for 200 For You and 100 Following results, processes all unseen results returned, and remembers every processed post ID for 30 days. Edit `~/.config/x-ai-brief/config.json` to change counts or the decision profile.

## State and recovery

```bash
python3 ~/.openclaw/skills/x-ai-brief/scripts/x_feed.py status
python3 ~/.openclaw/skills/x-ai-brief/scripts/x_feed.py prepare
python3 ~/.openclaw/skills/x-ai-brief/scripts/x_feed.py prepare --fresh
python3 ~/.openclaw/skills/x-ai-brief/scripts/x_feed.py reset --yes
```

A prepared run stays pending until the agent calls `commit`. If an agent turn crashes, the next run reuses the pending payload rather than losing those items. Committed payloads remain in `~/.openclaw/state/x-ai-brief/runs/` for 14 days for diagnosis.

## Security model

- X access is read-only; the collector only executes `home`, `check`, `whoami`, and optional diagnostic commands you run yourself.
- Feed content is treated as untrusted input and cannot authorize commands or writes.
- Cookie values are never written by this bundle. Browser-cookie extraction and X's undocumented GraphQL surface are still operational risks: X can break or rate-limit the client, so `xbird check` is the first diagnostic.

## Direct Hermes and Codex runners

When OpenClaw is not installed, `install.sh` installs a user-level systemd timer automatically. Hermes is preferred when available, with Codex CLI retained as the fallback. Both paths run the same two-phase collector at 08:00, 13:00, and 18:00 America/Denver, save Markdown briefs in `~/Documents/X AI Briefs/`, and emit a desktop notification when `notify-send` is available.

```bash
systemctl --user start x-ai-brief.service
systemctl --user status x-ai-brief.service
systemctl --user list-timers x-ai-brief.timer
less "$HOME/Documents/X AI Briefs/latest.md"
```

The direct Hermes run passes arbitrary snapshot content through a query file, strips X cookie variables from the agent environment, and saves only the final response from quiet mode. The direct Codex run uses a read-only sandbox and passes the feed on stdin as untrusted context. Both commit feed state only after a non-empty final briefing has been written.

Run either engine directly when needed:

```bash
./run-hermes.sh
./run-codex.sh
```
