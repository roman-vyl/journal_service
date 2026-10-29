## ADDED Requirements

### Requirement: Closed-trades table

The database SHALL contain a table `closed_trades` with primary key (`strategy_instance_id`, `trade_cycle_id`) and exactly the columns listed in this change's `design.md` (blocks 1–6), with the meaning, source and formula given there. Prices, quantities and money SHALL be stored as decimal text and times as UTC milliseconds. A column whose input is missing SHALL be null.

#### Scenario: New database
- **WHEN** the service creates a new database
- **THEN** it has schema version 2 with the `events` and `closed_trades` tables

#### Scenario: Upgrade keeps events
- **WHEN** the service opens a version 1 database holding events and a cursor
- **THEN** it adds an empty `closed_trades` table, sets version 2, and every event row and the cursor are unchanged

### Requirement: Formulas are fixed by this change

Any later change that fills `closed_trades` SHALL compute its columns with the formulas of this change's `design.md`, in decimal arithmetic. A formula SHALL be changed only by a new change approved by the owner.

#### Scenario: Real Demo short closed by stop
- **WHEN** a short trade has one entry execution `80496.1` × `3.818` with fee `169.03376039` and one stop-loss execution `80750` × `3.818` with fee `169.566925`
- **THEN** `gross_pnl_usdt` is `-969.3902`, `fees_usdt` is `338.60068539` and `net_pnl_usdt` is `-1307.99088539`

#### Scenario: Several fills
- **WHEN** the entry has executions 1 @ 100 and 3 @ 104
- **THEN** `entry_avg_price` is `103`, `entry_qty` is `4` and `entry_fill_count` is `2`
