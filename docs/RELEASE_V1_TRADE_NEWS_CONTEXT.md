# Historical trade news context

The Performance ledger now shows entry and exit news separately in its existing News context
cell. Each stage matches at most three stored articles tagged with the exact symbol during the
24 hours preceding that stage. Queries cover the relevant historical windows rather than
only the newest 500 articles. Overlapping query windows are merged, and combined API news
is deduplicated by article ID. A missing opening time stays unavailable.

These matches are made afterward and are labelled historical context. They do not prove
that a strategy read or used those articles. Certified automatic execution currently uses
technical signals; this release does not add news to its decisions or change execution.
Articles never collected cannot be recovered by this change. No decision-time snapshots
are introduced in this reporting-only release.

No schema migration, bridge restart or order changes are required. Recreate only the app,
retaining the IBKR protection Compose overlay. Verify health, migration head, existing broker
protection orders and entry/exit news in Performance. Roll back to the prior app image with
the same overlay if needed.

## Renderer scope correction

The news renderer resides inside the live-pages closure alongside its escaping and number
formatting helpers. Asset version 84.3 refreshes browser caches. Regression coverage executes
the full workspace script and Performance renderer, with populated, empty and failed API
responses, instead of supplying helpers that do not exist in the global browser scope.
