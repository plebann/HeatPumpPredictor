# Capability: forecast-temperature-validation

## Requirements

- The integration SHALL retain immutable hourly forecast snapshots separately from energy forecasts.
- Completed hourly windows SHALL be compared with the configured temperature sensor using a time-weighted mean from Recorder.
- Results with at least 60% valid coverage SHALL be marked `validated`; incomplete data SHALL remain `unvalidated` with a reason.
- A diagnostic sensor SHALL expose the last 14 days of horizon-range metrics and unique validated window count.
- When no validated data exists, the sensor state SHALL be `0` and every range SHALL have `windows: 0` with null metrics.
- The diagnostic description SHALL explicitly say “difference between point forecast and hourly average” and SHALL NOT present the value as correction-ready bias.
- Snapshot and result records SHALL be retained for 28 days and SHALL not alter forecast energy calculations.
