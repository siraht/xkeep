Yes — the previous plan was overbuilt for where we are. I would keep only a **tiny deterministic shell backbone** and let Hermes do the flexible work; there’s no reason to build `xfeed.py`, a failure taxonomy, repair-history machinery, or a custom orchestration layer before we know we need them.

I would **not** have Hermes itself perform every routine sync, though. Bird/Birdclaw already know exactly what commands to run, so asking an LLM every 30 minutes to decide how to run two deterministic commands adds cost and another failure mode for no benefit.

The whole system can be:

```text
systemd timer
    |
    v
sync.sh
    |
    +--> birdclaw sync Following
    +--> birdclaw sync For You
    +--> tiny provenance/rank modification
    |
    +--> success -> exit
    |
    +--> failure -> hermes chat -q "Fix this..."
```

Then separately:

```text
systemd timer / manual command
    |
    v
Hermes
    |
    +--> query Birdclaw/local DB
    +--> read interests.md
    +--> analyze everything since last digest
    +--> write digest.md
```

**What stays deterministic**

Only the pieces where determinism actually buys us something:

- systemd runs the schedule.

- A shell script runs fixed Birdclaw commands.

- Exit code `0` means success.

- Nonzero means failure.

- The DB modification preserves `following` vs `for_you` and rank.

- Hermes gets invoked when something breaks.

- Hermes can run the existing Birdclaw tests after changing code.

That might literally be a `sync.sh` around this size:

```bash
#!/usr/bin/env bash
set -euo pipefail

LOG="$HOME/.local/state/xfeed/sync.log"
mkdir -p "$(dirname "$LOG")"

if ! {
  birdclaw sync timeline \
    --mode bird \
    --limit 100 \
    --refresh

  birdclaw sync timeline \
    --mode bird \
    --for-you \
    --limit 100 \
    --refresh
} >>"$LOG" 2>&1
then
  tail -n 200 "$LOG" > /tmp/xfeed-failure.txt

  env -u AUTH_TOKEN -u CT0 \
    hermes chat -q "
The scheduled X feed sync failed.

Repository: /path/to/birdclaw
Failure log: /tmp/xfeed-failure.txt

Diagnose the failure. If this is a code problem, make the smallest
possible fix and run the relevant tests plus both timeline sync commands.

Do not modify credentials. Do not redesign the system. If this is an
expired login, X outage, or rate limit, report that instead of changing code.
"
fi
```

That's basically the backbone.

**I'd also simplify the Birdclaw modification.** We need only enough additional state to answer:

```text
tweet 123
  seen in Following: yes
  seen in For You: yes
  best For You rank: 7
  most recent For You rank: 12
  number of observations: 5
```

We don't need an elaborate event architecture. A tiny table such as:

```sql
feed_observations (
    tweet_id,
    feed,
    rank,
    observed_at
)
```

is enough.

**Hermes can own the digest almost entirely.** Give it a scheduled prompt along the lines of:

```text
Use the local Birdclaw database.

Analyze tweets collected since the previous digest from both Following
and For You. Deduplicate identical tweets but preserve feed provenance,
For You rank, and repeated appearances as relevance signals.

Read interests.md first.

Produce:
- Must know
- New tools/models/releases
- Research/technical developments
- Discussions worth knowing
- Worth reading
- Maybe

Collapse multiple tweets about the same development.
Include source links.
Write the result to digests/<timestamp>.md.
```

Hermes is exactly appropriate there because deciding **what matters** is fuzzy and contextual.

I would even defer automatic code repair for the first iteration. Initially:

1. **Scheduled sync shell script.**

2. **Scheduled Hermes digest.**

3. **If sync fails, scheduled/manual Hermes diagnosis with the log.**

4. Once we've seen actual recurring failure modes, automate only the ones that prove annoying.

That gets us from zero to useful with maybe **one Birdclaw patch, one shell script, two systemd units/timers, and two Hermes prompts**.

The dividing line is simple: **don't ask an agent to do something a shell command can do perfectly; don't write deterministic software for something an agent is much better at reasoning about.** That is the version I'd build first.
