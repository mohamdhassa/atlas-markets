# Strategy revision and rollback

Every manual symbol-strategy change is auditable.

## Revision events

- `CREATE`: initial configuration
- `UPDATE`: resulting configuration after a manual edit
- `ROLLBACK`: resulting configuration restored from a selected revision
- `DELETE`: final configuration immediately before deletion

Each revision stores the strategy owner, account, actor, timestamp, event, optional reason, and a complete parameter snapshot.

## API

- `GET /strategies/symbols/{strategy_id}/revisions` returns newest revisions first.
- `POST /strategies/symbols/{strategy_id}/rollback/{revision_number}` restores editable parameters.

Rollback never changes ownership, broker account, market, or symbol identity. The restored risk percentage is checked against the current administrator risk ceiling. A historical value that violates today's safety limit is rejected rather than silently applied.

## Operational rule

Use simulation accounts for evaluation. Revision history improves reproducibility and recovery; it does not guarantee profitability. Live execution remains controlled by the separate provider certification and explicit arming workflow.
