# ATLAS MARKETS v1.1 — Responsive Frontend

## Scope

This release makes the canonical v1 interface usable on phone, tablet and desktop without a
visual redesign. Existing colors, typography, cards, navigation labels, page content and
backend behavior are preserved.

## Changes

- One final responsive compatibility stylesheet owns viewport, overflow and touch behavior.
- Desktop grids progressively collapse for tablet and phone widths.
- Data tables remain horizontally scrollable instead of clipping columns.
- Charts, filters, forms, action rows and portfolio workspaces fit narrow viewports.
- The mobile sidebar has a backdrop, Escape handling, orientation handling and accessible
  expanded state.
- Initial application boot occurs after all page decorators load, preventing intermediate
  legacy layouts from flashing before the final page renderer.
- Safe-area padding and 44-pixel touch targets support modern mobile devices.
- The Portfolio trading universe uses separated two-column instrument cards on phones and a
  single column on very narrow screens, preventing symbol, market, mode and state text from
  collapsing into one continuous line.
- Portfolio grids and canvases are constrained to the available viewport width. Hero status
  pills retain their natural height, while the Performance button takes its own mobile row.
- Terminal candle labels now read provider `timestamp_ms` dates instead of inventing dates
  from array indices; missing dates remain unlabeled. Canvas resolution matches its CSS size.

## Page-by-page responsive audit

The final rendered page families were audited after all decorators and compatibility scripts load:

| Page family | Mobile behavior verified |
| --- | --- |
| Dashboard | Hero, runtime status, provider cards, metrics, alerts, and activity tables collapse without clipping. |
| Markets and Charts | Summaries collapse, toolbars remain touch-scrollable, and charts resize inside the viewport. |
| Signals and News | Signal cards, facts, headlines, and long decision text wrap safely. |
| Portfolio | KPIs, holdings, charts, timeframes, terminal, universe, and news context adapt without hiding broker data. |
| Orders and Performance | Broker tables retain every column through horizontal touch scrolling. |
| Accounts | Provider cards, facts, actions, account forms, and safety steps fit phone widths. |
| Operations | Health summaries, provider state, facts, actions, and activity logs stack predictably. |
| Users | User creation and the user table move to one column with full-size controls. |
| Strategy and Integrations | Editors, credentials, result output, provider actions, and wide management tables remain usable. |
| Risk and System | Metrics, policy panels, statuses, and dependency details collapse cleanly. |

Wide data tables intentionally scroll horizontally on phones instead of dropping columns or altering their meaning.

## Non-goals

- No brand or style redesign.
- No route, API, provider, strategy or database change.
- No removal of legacy frontend assets in this release.

## Acceptance

- Full Python test suite passes in the production-equivalent application image.
- Dashboard, Markets, Charts, Signals, Portfolio, Orders, Performance, Accounts, Operations,
  Users, Strategy, Risk, Integrations and System are checked at phone and desktop widths.
- Navigation opens, closes and routes correctly with mouse, touch and keyboard.
- No page introduces document-level horizontal overflow; wide tables scroll inside their
  existing containers.
