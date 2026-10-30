## MODIFIED Requirements

### Requirement: Health endpoint

The service MUST expose `GET /health` with status, cursor offset, last ingested
`occurred_at`, skipped and malformed line counts, and a `closed_trades` block with
`abi_configured`, the counts of `complete` and `incomplete` rows, the time of the last builder
pass and the error of the most recent failed attempt. Other endpoints are only those of the
`event-query` capability and the closed-trades read endpoints
(`/v1/closed-trades`, `/v1/closed-trades/{strategy_instance_id}/{trade_cycle_id}`).

#### Scenario: Health after ingestion
- **WHEN** the service has ingested events, skipped unrelated lines and met malformed ones
- **THEN** `GET /health` reports the cursor offset, the last ingested `occurred_at` and the skipped and malformed counts, and any path that is neither `/health`, an `event-query` path nor a closed-trades read path answers 404

#### Scenario: Health while ABI is down
- **WHEN** the last ABI request failed
- **THEN** `GET /health` answers `200` with ingestion status, and the `closed_trades` block shows the incomplete count and the error
