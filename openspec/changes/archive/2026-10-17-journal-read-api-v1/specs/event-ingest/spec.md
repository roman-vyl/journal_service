## MODIFIED Requirements

### Requirement: Health endpoint

The service MUST expose `GET /health` with status, cursor offset, last ingested
`occurred_at`, and skipped and malformed line counts. Other endpoints are only those of the
`event-query` capability.

#### Scenario: Health after ingestion
- **WHEN** the service has ingested events, skipped unrelated lines and met malformed ones
- **THEN** `GET /health` reports the cursor offset, the last ingested `occurred_at` and the skipped and malformed counts, and any path that is neither `/health` nor an `event-query` path answers 404
