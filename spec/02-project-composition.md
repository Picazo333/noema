# Project Composition

Projects are described through four composable dimensions:

1. **Project type** — dominant lifecycle class.
2. **Traits** — cross-cutting properties such as `visual`, `stateful`, or `agentic`.
3. **Quality claims** — properties the project claims and must evidence.
4. **Extensions** — namespaced domain metadata that Noema preserves without owning.

Profiles are initialization presets only. Projects materialize their effective type, traits, and claims into their own manifest and do not dynamically inherit later profile changes.
