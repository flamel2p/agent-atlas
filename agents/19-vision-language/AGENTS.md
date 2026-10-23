# Vision-Language case instructions

This directory owns the independently runnable Agent 19 demo. Read [SPEC.md](SPEC.md), [README.md](README.md), and [PLAN.md](PLAN.md) before editing. Root repository instructions also apply.

Keep implementation, dependencies, synthetic PNG fixtures, tests, scripts, and documentation here. Runtime must consume image pixels, never filename semantics, fixture truth, PNG metadata text, or sidecar labels. Test expectations belong outside the runtime package.

The selected backend is deterministic rectangular-diagram perception and a finite question grammar. Do not imply learned visual-language alignment or general VLM capability. Every exact answer is scoped to visible objects in the supported diagram grammar. Unknown scene content and the gray occluder require conservative uncertainty. Host policy alone decides whether an exact answer is allowed.

Use the root reviewer explanation standard. Define connected components, coordinates, provenance, uncertainty, limits, and component responsibilities where they matter. Add a linked source reading guide. Synchronize contract, behavior, checks, and docs. Do not change sibling cases or root governance.
