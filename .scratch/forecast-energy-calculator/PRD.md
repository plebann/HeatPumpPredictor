# Forecast Energy Calculator

Status: ready-for-agent

## Problem Statement

Heat Pump Predictor currently calculates `Forecast Energy` inside the Home Assistant coordinator. The coordinator parses the cached `Hourly Forecast`, selects the `Forecast Window`, determines the previous `Outdoor Temperature` for `Trend Adjustment`, calls the heat pump calculator for each forecast hour, applies the trend multiplier, counts `Approximated Prediction` hours, and shapes the response consumed by manual forecast service calls and `Scheduled Forecast` sensors.

From the user's perspective, this is risky because forecast behavior is harder to reason about and harder to test. The coordinator is supposed to be the Home Assistant adapter, but it currently owns core forecast calculation rules. A future change to Home Assistant setup, forecast cache refresh, or scheduled sensors can accidentally disturb forecast calculation. A future change to forecast calculation requires understanding Home Assistant coordinator details.

The architecture review and ADR-0001 decide that `Forecast Energy` needs its own deep module. The goal is to move forecast calculation behind a small deterministic interface while preserving the current Home Assistant response contract.

## Solution

Create a deep `ForecastEnergyCalculator` module responsible for calculating `Forecast Energy` from a cached `Hourly Forecast` and a `Forecast Window` request.

The Home Assistant coordinator remains the adapter. It continues to own forecast cache retrieval, Home Assistant state lookup, and conversion of domain forecast errors into Home Assistant validation errors. It passes the cached hourly forecast list, `starting_hour`, `hours_ahead`, optional current outdoor temperature, and an explicit `now` value into `ForecastEnergyCalculator`.

`ForecastEnergyCalculator` depends on the existing heat pump calculator supplied at construction time. It uses the existing heat pump calculator interface for interpolated power estimation and `Trend Adjustment`. It does not introduce a new forecast-hour calculator interface in this work.

The new module returns typed domain results internally. A serializer preserves the existing Home Assistant response dictionary exactly: field names, rounding, `hours` entries, `approximated_hours`, and `starting_hour` remain stable for service consumers and `Scheduled Forecast` sensors.

Domain forecast errors are represented by a single forecast calculation exception carrying a reason key and translation placeholders. The coordinator maps those reason keys to existing Home Assistant validation translation keys.

## User Stories

1. As a Home Assistant user, I want forecast energy calculation to keep returning the same fields, so that my automations and dashboards do not break.
2. As a Home Assistant user, I want scheduled forecast sensors to keep storing the same forecast attributes, so that historical scheduled forecast displays remain compatible.
3. As a Home Assistant user, I want forecast energy totals to be calculated the same way after the refactor, so that a structural change does not alter predictions.
4. As a Home Assistant user, I want forecast hour details to keep showing `datetime`, so that each prediction can be tied to a forecast hour.
5. As a Home Assistant user, I want forecast hour details to keep showing `temperature`, so that I can inspect the outdoor temperature used for each hour.
6. As a Home Assistant user, I want forecast hour details to keep showing `temperature_delta`, so that I can understand the hour-to-hour temperature movement.
7. As a Home Assistant user, I want forecast hour details to keep showing `trend_adjustment`, so that I can understand how rising or falling temperatures affected forecast energy.
8. As a Home Assistant user, I want forecast hour details to keep showing `energy_kwh`, so that I can inspect each hour's contribution to the total.
9. As a Home Assistant user, I want forecast hour details to keep showing `confidence`, so that I can judge how much observed data supports each prediction.
10. As a Home Assistant user, I want forecast hour details to keep showing `approximated`, so that I can detect hours based on nearby `Temperature Bucket` data.
11. As a Home Assistant user, I want forecast hour details to keep showing `approximation_source`, so that I can see which observed `Temperature Bucket` supported an approximated prediction.
12. As a Home Assistant user, I want `total_energy_kwh` rounding to remain stable, so that existing displays do not change unexpectedly.
13. As a Home Assistant user, I want hourly `energy_kwh` rounding to remain stable, so that scheduled forecast attributes remain comparable across versions.
14. As a Home Assistant user, I want `approximated_hours` to keep counting approximated forecast hours, so that I can see how much of the `Forecast Window` depends on approximated predictions.
15. As a Home Assistant user, I want `hours_requested` to keep echoing the requested window length, so that consumers can detect incomplete results.
16. As a Home Assistant user, I want `hours_returned` to keep reporting the number of forecast hours included, so that consumers can inspect the result shape.
17. As a Home Assistant user, I want `starting_hour` to keep echoing the requested local start hour, so that service responses remain self-describing.
18. As a Home Assistant user, I want the first future forecast entry matching `starting_hour` to remain the `Forecast Window` start, so that existing service behavior is preserved.
19. As a Home Assistant user, I want forecast entries to be sorted by datetime before selecting the `Forecast Window`, so that unordered weather provider output does not break predictions.
20. As a Home Assistant user, I want invalid forecast entries without parseable datetimes to be ignored as they are today, so that malformed non-window entries do not fail the whole forecast.
21. As a Home Assistant user, I want the forecast calculation to report the existing too-small-window error when no future start hour is available, so that I get a clear validation failure.
22. As a Home Assistant user, I want the forecast calculation to report the existing too-small-window error when the requested number of hours is unavailable, so that I know the cache is insufficient.
23. As a Home Assistant user, I want the forecast calculation to report the existing missing-hour error when a needed forecast hour has no temperature, so that I can diagnose bad forecast data.
24. As a Home Assistant user, I want the forecast calculation to report the existing missing-hour error when a forecast temperature cannot be parsed as a number, so that bad weather provider data is handled predictably.
25. As a Home Assistant user, I want the forecast calculation to report the existing no-data-for-approximation error when the heat pump calculator has no observed data to support prediction, so that I know the model needs history.
26. As a Home Assistant user, I want the forecast calculation to continue using current outdoor temperature for `Trend Adjustment` when the `Forecast Window` starts at the next hour, so that the first hour reflects the real current trend.
27. As a Home Assistant user, I want the forecast calculation to continue using the previous forecast hour temperature when the `Forecast Window` starts later, so that future windows do not depend on stale current conditions.
28. As a Home Assistant user, I want forecast windows that start later to fail when there is no previous forecast hour available, so that trend calculation is not based on missing data.
29. As a Home Assistant user, I want `Trend Adjustment` to remain based on the existing heat pump calculator behavior, so that temperature operating zones do not change during this refactor.
30. As a Home Assistant user, I want interpolated power estimation to remain based on the existing heat pump calculator behavior, so that `Temperature Bucket` prediction rules do not change during this refactor.
31. As a Home Assistant user, I want forecast temperatures outside observed `Temperature Bucket` history to continue producing `Approximated Prediction` results, so that natural weather forecasts still calculate.
32. As a Home Assistant user, I want forecast temperatures not to create `Temperature Bucket` history, so that forecasts remain predictions rather than observations.
33. As a Home Assistant user, I want the forecast cache sensor to keep refreshing the cache the same way, so that data acquisition remains stable.
34. As a Home Assistant user, I want `Scheduled Forecast` sensors to keep calling the coordinator method they call today, so that their Home Assistant lifecycle remains stable.
35. As a Home Assistant user, I want the manual forecast energy service to keep calling the coordinator method it calls today, so that Home Assistant service registration remains stable.
36. As a maintainer, I want forecast calculation rules in one module, so that changes to `Forecast Energy` have locality.
37. As a maintainer, I want the coordinator to stop owning `Forecast Window` selection, so that it can remain focused on Home Assistant adapter responsibilities.
38. As a maintainer, I want forecast calculation to accept an explicit `now`, so that tests do not patch clocks or depend on wall time.
39. As a maintainer, I want forecast calculation tests to use a fake heat pump calculator, so that tests isolate `Forecast Window` and `Trend Adjustment` orchestration.
40. As a maintainer, I want the heat pump calculator to remain the owner of interpolation and `Trend Adjustment`, so that this refactor does not mix in a second calculator redesign.
41. As a maintainer, I want typed forecast result objects inside the module, so that the implementation is easier to navigate than raw dictionaries.
42. As a maintainer, I want a serializer to the existing response dictionary, so that typed internals do not leak into the Home Assistant interface.
43. As a maintainer, I want one domain forecast exception type with reason keys, so that error mapping remains compact.
44. As a maintainer, I want the coordinator to map forecast domain errors to Home Assistant validation errors, so that the deep module does not know Home Assistant.
45. As a maintainer, I want tests at the new `ForecastEnergyCalculator` seam, so that most forecast behavior can be verified without Home Assistant setup.
46. As a maintainer, I want a thin adapter check around the coordinator, so that domain errors are mapped correctly without re-testing all forecast calculation paths through Home Assistant.
47. As a maintainer, I want no new weather forecast fetching behavior, so that this refactor stays structural.
48. As a maintainer, I want no new scheduled forecast schedules, so that this refactor stays focused on module depth.
49. As a maintainer, I want no new confidence vocabulary, so that forecast result semantics remain stable.
50. As a maintainer, I want the ADR decision reflected in the implementation, so that future architecture reviews do not move Home Assistant concerns back into the forecast module.

## Implementation Decisions

- Build a new `ForecastEnergyCalculator` module for `Forecast Energy` calculation.
- The new module is a deep module: it owns `Hourly Forecast` parsing, `Forecast Window` selection, previous-temperature selection, `Trend Adjustment` orchestration, per-hour result construction, total calculation, and approximated-hour counting.
- The coordinator remains the Home Assistant adapter. It owns forecast cache retrieval, Home Assistant current state lookup, and mapping forecast domain errors to Home Assistant validation errors.
- The forecast cache remains in the coordinator. The new module receives a cached `Hourly Forecast` list as input and does not fetch weather data.
- The new module receives an explicit `now` value from its caller. It does not read system time internally.
- The `ForecastEnergyCalculator` receives the existing heat pump calculator as a constructor dependency.
- The new module calls the existing heat pump calculator methods for interpolated estimation and `Trend Adjustment`.
- Do not add an `estimate_forecast_hour` heat pump calculator interface in this work. ADR-0001 deliberately defers that seam until reuse pressure proves it is real.
- The new module returns typed domain results internally, including a top-level forecast result and per-hour forecast entries.
- The typed result exposes a serializer that preserves the existing Home Assistant response dictionary exactly.
- The serialized top-level response must keep `total_energy_kwh`, `hours`, `hours_requested`, `hours_returned`, `approximated_hours`, and `starting_hour`.
- The serialized hour entries must keep `datetime`, `temperature`, `temperature_delta`, `trend_adjustment`, `energy_kwh`, `confidence`, `approximated`, and `approximation_source`.
- Existing rounding must be preserved: top-level `total_energy_kwh` and per-hour `energy_kwh` remain rounded as they are today.
- The `Forecast Window` start remains the first future forecast entry whose local hour equals the requested `starting_hour`.
- Forecast entries with unparseable datetimes continue to be ignored before window selection.
- Forecast entries are sorted by local datetime before window selection.
- If the `Forecast Window` starts at the next local hour, the first hour's previous temperature is the optional current outdoor temperature supplied by the caller.
- If the `Forecast Window` starts later than the next local hour, the first hour's previous temperature is taken from the forecast entry immediately before the window.
- If a later forecast window has no previous forecast entry, the module raises a forecast calculation error with the reason that maps to the existing too-small-window translation key.
- Missing forecast temperatures and unparseable forecast temperatures produce a forecast calculation error with the reason that maps to the existing missing-hour translation key and includes the affected datetime placeholder.
- No observed data for approximation produces a forecast calculation error with the reason that maps to the existing no-data-for-approximation translation key and includes the requested temperature placeholder.
- A missing or empty forecast cache is still handled by the coordinator before invoking the deep module, because cache availability is adapter state.
- The coordinator's public async method for calculating forecast energy remains available to manual service calls and `Scheduled Forecast` sensors.
- The manual forecast energy service and scheduled forecast sensors should not need to know the new module exists.
- The new domain forecast exception uses one exception class carrying a reason key and placeholders rather than one class per failure mode.
- No new Home Assistant translation keys are required unless implementation discovers a missing mapping. Existing forecast validation translation keys should be reused.
- ADR-0001 must remain true after implementation: the new module must not import Home Assistant modules.

## Testing Decisions

- Good tests should verify behavior through the `ForecastEnergyCalculator` interface rather than internal helper functions. The test should describe forecast outcomes, not the implementation's private parsing steps.
- The primary seam is the new `ForecastEnergyCalculator` module. This is the highest useful seam for forecast calculation because it exercises window selection, previous-temperature selection, trend orchestration, result construction, and domain error handling without Home Assistant setup.
- Tests at the primary seam should use a fake heat pump calculator adapter. The fake should provide deterministic interpolated estimation and trend adjustment values so the tests isolate `Forecast Energy` behavior.
- The fake heat pump calculator should be intentionally small: enough to record requested temperatures, return known estimation dictionaries, return known trend multipliers, and raise an approximation error when needed.
- Use explicit `now` values in tests. Do not patch global time or depend on wall-clock time.
- Test unordered hourly forecast input to prove forecast entries are sorted before `Forecast Window` selection.
- Test selection of the first future start hour matching `starting_hour`.
- Test too-small-window behavior when no start hour exists.
- Test too-small-window behavior when the requested `hours_ahead` exceeds available entries.
- Test missing temperature behavior with the datetime placeholder preserved.
- Test unparseable temperature behavior with the datetime placeholder preserved.
- Test current-temperature seeding when the window starts at the next hour.
- Test previous-forecast-hour seeding when the window starts later.
- Test `temperature_delta` and `trend_adjustment` values in serialized hour entries.
- Test total energy calculation after trend adjustment.
- Test `approximated_hours` counting.
- Test serialization preserves the existing response dictionary field names and rounding.
- Add a small coordinator adapter test only if practical in the existing test environment, focused on mapping forecast domain errors to Home Assistant validation errors. Do not duplicate every forecast calculation case through the coordinator.
- Existing calculator tests are prior art for parameterized calculator behavior, especially `Trend Adjustment`.
- Existing dynamic bucket tests are prior art for using focused seams without full Home Assistant setup when the behavior is domain logic.
- The full test suite should still pass in the repository's known local mode. If the local Home Assistant pytest plugin/socket issue persists, run the suite with plugin autoload disabled and document that limitation.

## Out of Scope

- Changing forecast cache retrieval is out of scope.
- Changing weather provider interaction is out of scope.
- Changing scheduled forecast schedules is out of scope.
- Changing the public Home Assistant forecast response dictionary is out of scope.
- Changing response field names is out of scope.
- Changing rounding behavior is out of scope.
- Changing `Trend Adjustment` rules is out of scope.
- Changing `Temperature Operating Zone` thresholds is out of scope.
- Changing interpolated estimation or `Approximated Prediction` behavior is out of scope.
- Creating `Temperature Bucket` history from forecast data is out of scope.
- Introducing a new `estimate_forecast_hour` heat pump calculator interface is out of scope.
- Introducing multiple forecast calculation strategies is out of scope.
- Introducing new confidence values is out of scope.
- Reworking `Scheduled Forecast` restore behavior is out of scope.
- Reworking the forecast cache sensor is out of scope.

## Further Notes

ADR-0001 is the architectural source of truth for this refactor. The central rule is that `ForecastEnergyCalculator` is a domain module and the coordinator is the Home Assistant adapter.

The key seam decision is intentionally conservative: deepen forecast calculation first, but do not redesign the heat pump calculator at the same time. The current heat pump calculator remains the source of interpolated estimation and `Trend Adjustment`.

The expected implementation should reduce coordinator complexity without changing user-visible forecast behavior.
