## MODIFIED Requirements

### Requirement: Health endpoint

The service MUST expose `GET /health` with status, cursor offset, last ingested
`occurred_at`, skipped and malformed line counts, and a `closed_trades` block with the counts
of `complete` and `incomplete` rows, whether the ABI base URL is configured, and the time and
error of the last ABI attempt. Other endpoints are only those of the `event-query` and
`closed-trades` capabilities.

#### Scenario: Health after ingestion
- **WHEN** the service has ingested events, skipped unrelated lines and met malformed ones
- **THEN** `GET /health` reports the cursor offset, the last ingested `occurred_at` and the skipped and malformed counts, and any path that is neither `/health` nor an `event-query` or `closed-trades` path answers 404

#### Scenario: Health with an ABI outage
- **WHEN** the last ABI request for an incomplete trade failed
- **THEN** `GET /health` still answers `200` with ingestion status, and the `closed_trades` block shows the incomplete count and the last error
