## 1. Read API

- [x] 1.1 Read module: list query with filters, order and limit (D1, D2, D4); one-row lookup; read-only connection.
- [x] 1.2 `health.py`: route `/v1/closed-trades` and `/v1/closed-trades/{sid}/{cid}`; 400 and 404 per D5.
- [x] 1.3 Tests: filters, order with incomplete rows, limit/truncated, row as stored (real Demo short `6072511f`), 400 cases, 404 cases, reads do not write.
- [x] 1.4 README: the two endpoints.

## 2. Rollout (on the owner's word only)

- [x] 2.1 PR and merge.
- [x] 2.2 bbb_stack `JOURNAL_IMAGE` pin as a separate PR; deploy on the owner's word.
