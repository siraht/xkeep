# Build log

This log records implementation progress, decisions, and lessons for `xkeep`.

## 2026-08-26

### Progress

- Imported `x-ai-brief.zip` unchanged as the baseline.
- Confirmed its collector test passes on Python 3.13.
- Confirmed the pinned `reorx/xbird` revision and documented `home --following` command contract still exist upstream.
- Confirmed the installed Hermes CLI supports quiet, non-interactive queries from a file.
- Added a direct Hermes runner, editable interests file, and timezone-correct systemd user timer.
- Added an end-to-end local check of the Hermes prepare, generate, save, and commit transaction.
- Bounded optional desktop notifications so a missing notification bus cannot stall a headless systemd run.
- Corrected systemd schedules to encode `America/Denver` in each calendar expression.
- Added a hidden-prompt credential helper for the common case where the authenticated browser runs on a different machine.
- Made remote credential entry accept both raw cookie values and Zen's labeled, quoted copy format.
- Verified the pinned `xbird` 1.2.0 revision against the real `@t_r_hinton` account.
- Completed a real 200-item For You plus 100-item Following collection: 294 unique unseen items, five cross-feed overlaps, all ranks retained, and no collector warnings.
- Completed a real Hermes briefing: six requested sections, 23 direct X links, a coverage statement, committed seen state, and no pending run.
- Installed and manually exercised the systemd user service. It exited successfully, produced a second real briefing, and left the timer enabled and waiting for the next America/Denver schedule.
- Migrated scheduling ownership to one native Hermes cron job with Telegram delivery and a resumed `xkeep-brief` session; retained the systemd installer only as an explicit fallback.
- Narrowed runtime installation to the files each runner actually needs after a stale copied `.git` directory blocked an update.
- Made Hermes timezone refresh target the PID recorded by Hermes itself, so it works with either systemd or an external gateway supervisor without requiring root.
- Restored one stable `xkeep-brief` session so every scheduled briefing appears in the same Hermes Desktop chat; Hermes handles context compression as needed.

### Decisions

- Preserve all OpenClaw and Codex behavior from the baseline; add Hermes support instead of replacing existing integrations.
- Keep the collector's prepare/commit state transition. It is slightly more code than the original plan's shell sketch, but prevents failed briefing runs from silently consuming feed items.
- Keep feed provenance and rank on each normalized item rather than patching an external Birdclaw database. The local staged and archived run files provide the same evidence without coupling `xkeep` to another repository's schema.
- Use systemd user timers for direct local scheduling and set `Timezone=America/Denver` explicitly.
- Prefer Hermes when OpenClaw is unavailable while retaining the generated Codex fallback.
- Keep failure recovery conservative for the first release: systemd retains the complete journal and failed feed runs remain pending. Do not add automatic code mutation until a recurring, safely repairable failure is observed.
- Prefer one stable Desktop conversation over independent briefing contexts; it is the user-facing continuity that matters here.

### Lessons

- The baseline already reviews the complete bounded snapshot, deduplicates posts while preserving both feed positions, and commits seen state only after successful output.
- The original plan named Birdclaw, but the delivered baseline targets the actively maintained Linux-compatible `reorx/xbird`. Supporting its documented interface keeps the project self-contained.
- Optional desktop integrations need explicit time bounds under user services; command availability alone does not guarantee a reachable desktop bus.
- systemd timer units do not have a standalone `Timezone=` key; timezone-qualified `OnCalendar=` expressions are the portable form.
- Copying a whole browser cookie database is unnecessary and overbroad; the remote collector needs only X's `auth_token` and `ct0` values.
- Personalized X snapshots can churn substantially within minutes. Transactional seen-state and full-snapshot review are useful; pretending the feed is a canonical, exhaustively synchronizable stream would be misleading.
- Runtime installers should install runtime files, not clone repository metadata and source archives into application state.
- A machine can have more than one Hermes gateway supervisor configured. The scheduler should follow Hermes' live PID file instead of guessing which service owns the active gateway.
- Hermes single-query mode treats `/new` as model input rather than a slash command. A new unnamed invocation followed by a deterministic rename gives recurring briefs clean context without depending on the interactive command loop.
- Hermes session titles are unique. Preserving one stable title with fresh contexts requires a transactional title swap: archive the predecessor by ID, promote the successful new session, and restore the predecessor on failure.
