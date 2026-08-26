# Provenance

- The authenticated timeline transport is compatible with `reorx/xbird`, pinned by the installer to commit `dfc5040ea0c5f4885ed3102ba282a8188d170278` (August 10, 2026). `xbird` is an MIT-licensed Python rewrite of `@steipete/bird` v0.8.1.
- The local skill is original code created for this bundle. It does not include code copied from the community `x-timeline-digest` skill.
- The design deliberately changes that community skill's behavior: every unseen bounded-snapshot item reaches the model; no engagement-based pre-truncation occurs; and state uses prepare/commit rather than optimistic pre-delivery mutation.
