# Greenhouse Data Contracts

This directory is the versioned interface between sensors, the state service,
Omniverse, operator tools, controllers, and Cosmos. Version 1 uses JSON Schema
Draft 2020-12.

## Contracts

- `v1/device-registry.schema.json`: stable zones, devices, capabilities, and USD mappings.
- `v1/telemetry-event.schema.json`: one timestamped observation from one device.
- `v1/greenhouse-snapshot.schema.json`: synchronized context for UI and Cosmos.
- `v1/command.schema.json`: validated actuator command and its lifecycle.
- `v1/cosmos-decision.schema.json`: Cosmos explanation and proposed actions.

The contracts deliberately separate four concepts:

1. **Configuration** describes what exists and where it is located.
2. **Telemetry** records what a device observed.
3. **Reported state** records what an actuator says it is doing.
4. **Commands** request a change. A Cosmos proposal is not a command.

All timestamps are UTC RFC 3339 strings. Normalized positions, speeds, and
moisture values use the inclusive range `0.0` to `1.0`. Missing or stale data
must be represented by quality metadata; consumers must not invent defaults.

`config/greenhouse.registry.json` is the initial project registry. Run
`scripts/validate_data_contracts.sh` to check JSON syntax, schema identity,
stable IDs, references, and USD path conventions without installing packages.

