## MODIFIED Requirements

### Requirement: Events are indexed, not interpreted

The `events` table MUST hold producer events as received. The service MUST NOT derive events from another service's internal state or correlation snapshots, compute what Engine wanted, or determine an order or position state. The only derived data the service MAY keep is the `closed_trades` table of the `closed-trades` capability; it MUST NOT write derived data into `events`.

#### Scenario: A new fact is needed
- **WHEN** a feature needs a fact that no producer journals yet
- **THEN** the producing service is changed to journal it, and the Central Journal only learns to accept the new `event_type`

#### Scenario: Derived data stays out of events
- **WHEN** closed-trade data exists
- **THEN** it is only in `closed_trades`, and `events` holds producer lines only
