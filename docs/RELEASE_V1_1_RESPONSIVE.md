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
