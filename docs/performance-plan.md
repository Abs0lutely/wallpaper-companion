# Runtime efficiency acceptance contract

Base: 2055adf594949747f4ac47d5396311efd95eb0f2. Worktree: wallpaper-companion-perf; branch: perf/runtime-efficiency.

Preserve the existing visual style, feature entrypoints, JSON data, extension APIs, audio/WE behavior and secrets/data protection. Optimize only the desktop application, not GPT-SoVITS. Do not publish or replace personal installations.

Implement deferred editing pages, tray startup without editor widgets, bounded shared audio snapshots with external-change reconciliation, record-backed resource tables, bounded thumbnail reuse, and separated bounded short-query/background queues. GUI widgets and players remain on the Qt thread. Preserve autosave/undo, hidden selection/checks, scope changes and stale-callback handling. Playback must continue without opening any configuration page.

Measure source startup, tray readiness, first deferred access, memory (private and working set/peak), CPU, operation/GUI latency, and background queue contention. Fixed empty/normal/large fixtures; five repeated short runs, ten-minute idle and thirty-minute stress. Compare identical environments; retain only repeatable improvements, disclose regressions and simulated versus real checks. Preserve raw reports and reproducible commands. Benchmark fixtures never contact real WE/model services.

Use existing isolated unit/UI validation and targeted regression cases for deferred-page state, invalidation, bounded queues, list identity and cleanup. Review standards and this spec against the fixed base. Deliver local commits and a comparison report. Later integrate completed auto-update work in a separate integration branch after the other chat finishes; do not merge its moving branch.
