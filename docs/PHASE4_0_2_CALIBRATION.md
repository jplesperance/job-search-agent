# Phase 4.0.2 Calibration

This patch tightens discovery based on the second live watchlist run.

Changes:

- expands JD salary extraction to recognize compensation sections where the numeric range is separated from the label by explanatory prose;
- inspects Greenhouse-exposed metadata for salary/pay custom fields when present;
- strengthens heavy-coding detection for security roles that explicitly require daily production coding, production-grade code, real code/scripts, or custom offensive tooling/exploits;
- preserves security management roles such as Engineering Manager, Proactive Security when coding is not a core individual-contributor responsibility;
- counts analyzed, hard-filter-passed, and surfaced jobs by unique persisted job ID so run totals match the candidate list.

The policy remains intentionally permissive for ordinary security automation and scripting. A single Python/Go mention is not enough to reject a role.
