# Connected knowledge phase

Status: provisional architecture; X methodology research blocked on Grok Build authentication. No research findings or popularity claims have been verified yet. Do not treat this document as the requested completed research memo.

## Outcome

Keep the current Hermes/Telegram briefing operational. Add an independent pipeline that interprets archived feed posts against accumulated knowledge, maintains linked topic pages and evidence-backed claims, and offers a mobile-friendly reading interface plus a contextual change report.

## Research prerequisite

On 2026-11-09 the installed Grok Build CLI rejected the first research request with HTTP 401, invalid or expired credentials, no authentication context. No X search results were obtained. The CLI supports `grok login --device-auth` for this remote host.

Once authenticated, use a small set of targeted X searches covering Karpathy's LLM wiki, agent-maintained ontologies, temporal knowledge graphs, GraphRAG, entity resolution, and personal knowledge systems. Prefer respected practitioners and posts with observed engagement, but record dates and actual counts rather than treating popularity as proof. For each method record the exact post URL, author, linked primary implementation, concrete workflow, evidence, limitations, and applicability here. Distinguish observations from recommendations. Save findings in a separate research Markdown document before finalizing implementation choices.

## Existing evidence and integration boundary

The collector already archives normalized JSON snapshots under `~/.openclaw/state/x-ai-brief/runs/`. Records contain run IDs, timestamps, original post IDs, URLs, authors, text, quoted posts, metrics, feed provenance and ranks. Recent archived snapshots are available for development; no new personal-feed query is necessary.

Archives are pruned according to the existing retention policy. The new pipeline must copy source evidence into its own durable private store as it imports each committed archive. It must never modify original snapshots or the original seen-state ledger. Archive discovery and import use a separate cursor; a failed enrichment attempt must remain retryable without repeating existing Telegram briefings. Recovering material already pruned is outside the available archive history.

## Provisional implementation sequence

1. Research and compare current approaches, then write a source-linked decision record.
2. Build an independent archive importer with idempotence by run ID and post ID. Store raw evidence and import history in a private directory excluded from Git.
3. Use an agent to propose structured changes against retrieved existing topics and claims. Resolve entities by stable IDs and aliases; retrieve by names and full-text search initially. Add semantic retrieval only if measured misses justify it.
4. Validate and atomically apply proposed updates: entities, claims, source references, relationships, topic memberships and revisions. Every factual claim must cite retained source evidence. Treat tweets as untrusted content, with attributed claims distinguished from verified facts.
5. Maintain evolving topic pages and a change journal. New evidence may support, contradict, refine or supersede earlier claims. Preserve previous versions and temporal context; never silently overwrite a disputed assertion. Merge and split topics with redirects and retained provenance, so ontology changes do not break old references.
6. Generate a contextual digest from applied changes: what is new, what changed, what contradicts prior coverage, and useful cross-topic connections. Label inferred connections as analysis. Keep one story per paragraph and omit filtering commentary.
7. Add a responsive reading interface with search, topic pages, source links, timelines, related topics and a since-last-visit view. A graph view is optional navigation, not the primary reading experience. Private feed contents must not become public through the public code repository or unauthenticated hosting.
8. Exercise the full pipeline against archived snapshots, including a replay proving no duplicate claims or reports, a failed update proving retry safety, and citations linking back to retained sources. Compare generated classifications and connections manually with actual post text.
9. Enable a separate scheduled job only after the archive-backed path works. Keep its state, execution errors and delivery distinct from the original job. Verify the new interface and contextual report with a real completed import.

## Acceptance criteria

- Existing briefing job and state continue working without dependency on the new pipeline.
- Previously imported posts are not processed as new on replay.
- Every factual page statement and relationship has traceable source evidence or an explicit inference label.
- Conflicting and superseded information remains inspectable.
- Topic reorganization preserves stable links and revision history.
- Search, readable pages and recent changes work on desktop and mobile widths.
- Research, design decisions, implementation progress and remaining limitations are documented honestly.
