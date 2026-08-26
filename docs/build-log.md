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

### Decisions

- Preserve all OpenClaw and Codex behavior from the baseline; add Hermes support instead of replacing existing integrations.
- Keep the collector's prepare/commit state transition. It is slightly more code than the original plan's shell sketch, but prevents failed briefing runs from silently consuming feed items.
- Keep feed provenance and rank on each normalized item rather than patching an external Birdclaw database. The local staged and archived run files provide the same evidence without coupling `xkeep` to another repository's schema.
- Use systemd user timers for direct local scheduling and set `Timezone=America/Denver` explicitly.
- Prefer Hermes when OpenClaw is unavailable while retaining the generated Codex fallback.

### Lessons

- The baseline already reviews the complete bounded snapshot, deduplicates posts while preserving both feed positions, and commits seen state only after successful output.
- The original plan named Birdclaw, but the delivered baseline targets the actively maintained Linux-compatible `reorx/xbird`. Supporting its documented interface keeps the project self-contained.
- Optional desktop integrations need explicit time bounds under user services; command availability alone does not guarantee a reachable desktop bus.
