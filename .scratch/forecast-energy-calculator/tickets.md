# Tickets: Forecast Energy Calculator

Status: ready-for-agent

Build a deep `ForecastEnergyCalculator` module for `Forecast Energy`, preserving the current Home Assistant response contract. Source spec: `.scratch/forecast-energy-calculator/PRD.md`.

Work the **frontier**: any ticket whose blockers are all done. For this linear chain, work top to bottom.

## Create Forecast Energy seam

**What to build:** A new `ForecastEnergyCalculator` module can calculate one complete `Forecast Energy` response from cached `Hourly Forecast`, `Forecast Window` inputs, explicit `now`, optional current `Outdoor Temperature`, and a fake heat pump calculator in tests. It preserves response fields and rounding without changing coordinator behavior yet.

**Blocked by:** None — can start immediately.

- [ ] `ForecastEnergyCalculator` accepts cached `Hourly Forecast`, `starting_hour`, `hours_ahead`, optional current `Outdoor Temperature`, and explicit `now`.
- [ ] The module receives the existing heat pump calculator as a constructor dependency.
- [ ] The happy path selects the first future `Forecast Window` matching `starting_hour`.
- [ ] Forecast entries are sorted by datetime before selecting the `Forecast Window`.
- [ ] The result serializes to the existing response dictionary fields.
- [ ] Top-level and hourly energy rounding match current behavior.
- [ ] Tests cover the happy path through the `ForecastEnergyCalculator` seam with a fake heat pump calculator.

## Move forecast error semantics behind domain errors

**What to build:** Forecast failures from the new module use one domain exception with reason keys and placeholders, and tests cover the forecast error cases through the `ForecastEnergyCalculator` seam.

**Blocked by:** Create Forecast Energy seam.

- [ ] A single forecast calculation exception carries a reason key and translation placeholders.
- [ ] Missing or too-small `Forecast Window` raises a reason that maps to the existing too-small-window validation message.
- [ ] Missing forecast temperature raises a reason that maps to the existing missing-hour validation message with datetime placeholder.
- [ ] Unparseable forecast temperature raises a reason that maps to the existing missing-hour validation message with datetime placeholder.
- [ ] No observed data for approximation raises a reason that maps to the existing no-data-for-approximation validation message with temperature placeholder.
- [ ] Tests use explicit `now` values and do not patch global time.

## Adapt coordinator to ForecastEnergyCalculator

**What to build:** `HeatPumpCoordinator.async_calculate_forecast_energy` delegates calculation to the deep module, keeps forecast cache and Home Assistant validation mapping, and preserves the public dictionary contract for manual forecast calls and `Scheduled Forecast` sensors.

**Blocked by:** Move forecast error semantics behind domain errors.

- [ ] The coordinator still handles missing or empty forecast cache before invoking the deep module.
- [ ] The coordinator passes cached `Hourly Forecast`, request inputs, current `Outdoor Temperature`, and explicit `now` into `ForecastEnergyCalculator`.
- [ ] The coordinator maps forecast domain errors to `ServiceValidationError` using existing translation keys and placeholders.
- [ ] The coordinator no longer owns `Forecast Window` selection or per-hour result shaping.
- [ ] Manual forecast service callers keep receiving the same response dictionary shape.
- [ ] `Scheduled Forecast` sensors keep using the coordinator method unchanged.

## Verify scheduled forecast and service compatibility

**What to build:** Existing `Scheduled Forecast` and manual forecast service behavior remains compatible after the coordinator delegates to the deep module.

**Blocked by:** Adapt coordinator to ForecastEnergyCalculator.

- [ ] Manual forecast service behavior preserves response fields, rounding, and error translation keys.
- [ ] `Scheduled Forecast` sensors keep storing the same attributes and state values.
- [ ] Forecast calculation does not create `Temperature Bucket` history.
- [ ] Forecast cache refresh behavior is unchanged.
- [ ] Forecast temperatures outside observed `Temperature Bucket` history still produce `Approximated Prediction` results when the heat pump calculator can approximate.
- [ ] Existing tests for calculator, dynamic buckets, sensor builders, and performance curves still pass.

## Clean up coordinator forecast locality

**What to build:** Coordinator forecast code is simplified so `Forecast Energy` rules live behind the new deep module and ADR-0001 remains true.

**Blocked by:** Verify scheduled forecast and service compatibility.

- [ ] `HeatPumpCoordinator` no longer contains `Hourly Forecast` parsing logic.
- [ ] `HeatPumpCoordinator` no longer contains `Forecast Window` selection logic.
- [ ] `HeatPumpCoordinator` no longer contains previous-temperature selection for `Trend Adjustment`.
- [ ] `HeatPumpCoordinator` no longer contains `Trend Adjustment` orchestration for forecast hours.
- [ ] `HeatPumpCoordinator` no longer contains per-hour `Forecast Energy` result shaping.
- [ ] The new `ForecastEnergyCalculator` module does not import Home Assistant modules.
- [ ] Tests document the `ForecastEnergyCalculator` seam as the primary forecast calculation test surface.
