# Dynamic Temperature Buckets

Status: ready-for-agent

## Problem Statement

Heat Pump Predictor currently behaves as though the integration has a fixed supported outdoor temperature range. Historical temperature buckets are pre-created for a fixed span, observed outdoor temperatures outside that span are clamped into edge buckets, manual energy calculations are validated against the same fixed span, and performance curve data is assembled by iterating that static range.

From the user's perspective, this makes the learned performance model less trustworthy. If the observed outdoor temperature moves below or above the current hard-coded span, the integration should not pretend that the observation happened at the nearest supported edge. The observed heat pump should be modeled at the outdoor temperatures that actually occur.

The user wants temperature buckets to be dynamic. A temperature bucket should be historical: it should be created from observed outdoor temperature readings when previous-state attribution assigns observed time to that bucket. Hourly forecasts and manual service requests should use the learned history for prediction, but should not create historical buckets.

## Solution

The integration will replace the fixed supported temperature range with dynamic temperature buckets derived from observed outdoor temperature readings. Bucket `N` covers outdoor temperatures from `N°C` inclusive up to `N+1°C` exclusive. Observed outdoor temperatures are not clamped to a fixed range.

When previous-state attribution assigns elapsed observed time to a temperature bucket that does not yet exist, the integration creates that bucket. Once the bucket has observed time, it participates in power curve, duty cycle curve, energy distribution, approximation, service range calculation, and per-bucket Home Assistant sensor creation.

Manual energy calculation keeps a deliberate guardrail, but that guardrail is no longer a fixed integration temperature limit. The service prediction range is dynamic: the inclusive span from five degrees below the lowest temperature bucket with observed time to five degrees above the highest temperature bucket with observed time. If no bucket has observed time, the service returns a no-data validation error.

Hourly forecast energy calculation has no outdoor temperature range limit. Forecast temperatures do not create temperature buckets. If a forecast temperature has no directly observed bucket, the calculation produces an approximated prediction from the nearest observed temperature bucket and reports the existing `approximated` confidence behavior.

Per-bucket Home Assistant sensors become dynamic. They are created for temperature buckets with observed time, including newly observed buckets after setup. Empty legacy buckets may remain in stored data, but they do not count as observed buckets and do not produce per-bucket sensors.

## User Stories

1. As a Home Assistant user, I want the integration to record heat pump behavior at the outdoor temperatures that actually occur, so that extreme weather is not collapsed into an artificial edge bucket.
2. As a Home Assistant user, I want temperature buckets to appear dynamically as my outdoor temperature sensor reports new whole-degree bands, so that the performance model grows with my real environment.
3. As a Home Assistant user, I want a temperature below the old minimum range to create its own bucket when observed time is assigned, so that cold-weather behavior is modeled separately.
4. As a Home Assistant user, I want a temperature above the old maximum range to create its own bucket when observed time is assigned, so that hot-weather behavior is modeled separately.
5. As a Home Assistant user, I want fractional outdoor temperatures to map consistently to whole-degree buckets, so that `3.9°C` and `3.1°C` are grouped in bucket `3`.
6. As a Home Assistant user, I want negative fractional temperatures to map using the same bucket rule, so that `-0.1°C` belongs to bucket `-1` rather than being treated as `0`.
7. As a Home Assistant user, I want previous-state attribution to continue assigning elapsed time and energy to the prior outdoor temperature bucket, so that dynamic bucket creation does not change the attribution rule.
8. As a Home Assistant user, I want the first observation to initialize tracking without inventing observed time, so that bucket data only reflects elapsed periods.
9. As a Home Assistant user, I want a new bucket to count as observed only after it receives total time, so that a single instantaneous temperature reading does not expand prediction support by itself.
10. As a Home Assistant user, I want running time to continue accumulating only when the observed heat pump was running, so that duty cycle remains meaningful in dynamic buckets.
11. As a Home Assistant user, I want total time to include running and idle observed periods in dynamic buckets, so that overall power remains comparable across temperatures.
12. As a Home Assistant user, I want energy readings to continue accumulating into the attributed bucket when energy changes, so that energy distribution remains historically grounded.
13. As a Home Assistant user, I want dynamic buckets to survive Home Assistant restart once they contain observed data, so that learned history is not lost.
14. As a Home Assistant user, I want old stored empty buckets to be harmless, so that upgrading from the fixed range model does not create misleading entities.
15. As a Home Assistant user, I want old stored buckets with observed time to remain usable, so that existing learned history carries forward.
16. As a Home Assistant user, I want the power curve to include all dynamic buckets with observed time, so that charts reflect the actual learned outdoor temperature span.
17. As a Home Assistant user, I want the duty cycle curve to include all dynamic buckets with observed time, so that runtime behavior is visible across the learned span.
18. As a Home Assistant user, I want the energy distribution to include all dynamic buckets with observed energy, so that observed consumption is shown at the temperatures where it occurred.
19. As a Home Assistant user, I want curve data sorted by outdoor temperature, so that chart consumers can render a natural temperature axis.
20. As a Home Assistant user, I want per-bucket energy sensors only for buckets with observed time, so that my entity registry is not filled with empty temperature bands.
21. As a Home Assistant user, I want per-bucket running power sensors only for observed buckets, so that each exposed entity corresponds to learned behavior.
22. As a Home Assistant user, I want per-bucket overall power sensors only for observed buckets, so that exposed metrics are tied to actual observations.
23. As a Home Assistant user, I want per-bucket duty cycle sensors only for observed buckets, so that duty cycle entities are not created before there is any elapsed time.
24. As a Home Assistant user, I want sensors for newly observed buckets to appear without restarting Home Assistant, so that the UI catches up as the model learns.
25. As a Home Assistant user, I want dynamic per-bucket sensors to keep stable unique IDs, so that entity customization remains reliable after reloads.
26. As a Home Assistant user, I want dynamic per-bucket sensors to keep translated names, so that the integration remains compatible with Home Assistant entity naming expectations.
27. As a Home Assistant user, I want the manual energy calculation service to accept temperatures near the learned history, so that I can ask practical what-if questions.
28. As a Home Assistant user, I want the manual service range to extend five degrees below my lowest observed bucket, so that nearby colder scenarios can be approximated.
29. As a Home Assistant user, I want the manual service range to extend five degrees above my highest observed bucket, so that nearby warmer scenarios can be approximated.
30. As a Home Assistant user, I want the manual service range to be inclusive, so that boundary values exactly five degrees outside history are accepted.
31. As a Home Assistant user, I want the manual service to reject requests outside the dynamic service prediction range, so that it does not present far extrapolation as a normal user-requested estimate.
32. As a Home Assistant user, I want the manual service to return a no-data error before any bucket has observed time, so that I know the model has not learned enough to answer.
33. As a Home Assistant user, I want accepted manual service requests for unobserved temperatures to use the nearest observed bucket, so that the service can still provide approximated predictions.
34. As a Home Assistant user, I want manual service responses to continue reporting approximation source, so that I can see which observed bucket supported the estimate.
35. As a Home Assistant user, I want manual service responses to continue reporting data hours, so that I can judge how much observation supports the answer.
36. As a Home Assistant user, I want forecast energy calculation to accept any outdoor temperature returned by the weather forecast, so that natural weather data does not fail because of an artificial range.
37. As a Home Assistant user, I want forecast temperatures not to create historical temperature buckets, so that forecasts do not pollute observed heat pump history.
38. As a Home Assistant user, I want forecast temperatures outside the observed bucket span to be approximated from the nearest observed bucket, so that scheduled forecast energy continues to produce a result.
39. As a Home Assistant user, I want forecast hour details to keep reporting whether a prediction was approximated, so that downstream automations can inspect prediction confidence.
40. As a Home Assistant user, I want forecast hour details to keep reporting approximation source, so that I can understand which observed bucket supported each forecast hour.
41. As a Home Assistant user, I want trend adjustment to remain based on temperature operating zones, so that heating, neutral, and cooling behavior does not change as part of dynamic buckets.
42. As a Home Assistant user, I want trend adjustment to continue using hour-to-hour forecast temperature deltas, so that rising or falling forecast temperatures influence forecast energy.
43. As a Home Assistant user, I want dynamic bucket behavior to avoid changing weather forecast retrieval, so that existing forecast cache behavior remains stable.
44. As a Home Assistant user, I want scheduled forecasts to continue restoring their last value and attributes, so that dynamic buckets do not disrupt scheduled forecast sensors.
45. As a Home Assistant user, I want the integration to preserve HACS and Home Assistant entity conventions, so that dynamic sensors remain manageable in Home Assistant.
46. As a Home Assistant user, I want stored data serialization to remain backward compatible with existing bucket data, so that upgrades do not require manually clearing storage.
47. As a Home Assistant user, I want restored tracking state to continue working, so that previous-state attribution remains correct after restart.
48. As a Home Assistant user, I want dynamic buckets to avoid duplicate sensor creation, so that repeated observations of the same temperature bucket do not create duplicate entities.
49. As a Home Assistant user, I want unloaded integration entries to clean up correctly, so that dynamic entity creation does not leave stale runtime callbacks.
50. As a Home Assistant user, I want the integration logs to remain useful when dynamic service range validation fails, so that I can diagnose why a manual request was rejected.
51. As a Home Assistant user, I want existing low, medium, high, and approximated confidence behavior to remain understandable, so that dashboards and automations do not need a new confidence vocabulary.
52. As a Home Assistant user, I want dynamic buckets to work for both cold and hot climates, so that the integration adapts to local conditions rather than a developer-chosen range.

## Implementation Decisions

- Temperature bucket creation moves from eager fixed-range initialization to lazy creation from observed outdoor temperature readings.
- The bucket key remains a whole-degree integer derived with floor semantics. Bucket `N` covers `N°C` inclusive up to `N+1°C` exclusive.
- Previous-state attribution remains the rule for assigning total time, running time, and energy. The previous outdoor temperature determines which bucket receives the elapsed observation.
- A bucket counts as observed for service range, sensor creation, and curve inclusion only when it has total time greater than zero.
- The data manager becomes the owner of dynamic bucket lifecycle. It should provide operations that get or create an observed bucket during attribution, read existing buckets safely, and enumerate observed buckets in temperature order.
- The calculator no longer iterates a fixed temperature range. Approximation should search observed buckets and choose the nearest source bucket.
- Direct estimation for a temperature should not create a bucket. It should use direct observed bucket data if that bucket exists with observed time; otherwise it should return an approximated prediction from the nearest observed bucket.
- Interpolation should not clamp lower and upper bounds to a fixed range. It should interpolate between estimates for the mathematical floor and ceiling buckets when appropriate, while still allowing each side to be approximated from observed history.
- The manual energy calculation service removes the fixed schema min/max validation. Service range validation must happen at runtime because it depends on observed bucket data.
- The manual energy calculation service accepts only temperatures inside the dynamic service prediction range: lowest observed-time bucket minus five through highest observed-time bucket plus five, inclusive.
- When no bucket has observed time, the manual energy calculation service returns the existing no-data style validation error rather than accepting a request it cannot support.
- Hourly forecast energy calculation does not validate forecast temperatures against the service prediction range.
- Hourly forecast energy calculation does not create temperature buckets.
- Scheduled forecast energy calculation inherits the same forecast behavior and should not create temperature buckets.
- Forecast predictions outside the observed span continue to be represented using the existing approximated prediction behavior. No new confidence value or separate extrapolation field is required.
- Temperature operating zones for trend adjustment remain unchanged: heating at `17°C` and below, neutral from `18°C` through `22°C`, and cooling at `23°C` and above.
- Per-bucket Home Assistant sensors should be created for buckets with observed time. This applies during platform setup for restored buckets and at runtime when a new observed bucket first receives total time.
- Runtime creation of per-bucket sensors needs an integration-level mechanism that can notify the sensor platform when a newly observed bucket becomes sensor-worthy.
- Sensor creation must be idempotent. The integration should track which bucket temperatures already have per-bucket entities for an entry.
- Performance curve sensors enumerate dynamic observed buckets in ascending temperature order rather than iterating a fixed temperature span.
- Storage can remain backward compatible with old fixed-range bucket data. Empty restored buckets may remain in memory/storage, but they are not observed buckets and do not create entities.
- Constants representing the old fixed supported temperature range should no longer define bucket lifecycle, service schema validation, calculator approximation, interpolation, or curve iteration.
- Entity naming and translation patterns remain unchanged. Dynamic per-bucket sensors must still use translated names, stable unique IDs, `_attr_has_entity_name`, and disabled-by-default per-bucket entities as appropriate.
- Existing service response fields remain stable: energy, running power, overall power, duty cycle, temperature bucket, confidence, approximated flag, approximation source, and data hours.

## Testing Decisions

- Tests should focus on external behavior: which bucket receives observed time and energy, which predictions are accepted or rejected, which service responses are returned, and which sensor entities appear. Tests should avoid asserting private implementation details such as the exact internal helper used to create a bucket.
- The highest-value seam is the integration behavior around state updates, services, and sensors. This seam verifies dynamic bucket creation, runtime entity creation, service range validation, and forecast calculation in the same shape Home Assistant users experience.
- A focused data manager seam is appropriate for previous-state attribution and dynamic bucket creation because this logic is domain-critical and can be tested without Home Assistant setup overhead.
- A focused calculator seam is appropriate for approximation and interpolation behavior because the repository already has calculator-level test prior art for trend adjustment.
- Service tests should cover `calculate_energy` with no observed buckets, inside the dynamic service prediction range, exactly at both inclusive boundaries, and outside both boundaries.
- Forecast tests should cover forecast temperatures outside the observed bucket span and confirm they calculate as approximated predictions without creating buckets.
- Sensor platform tests should cover initial setup with restored observed buckets and runtime creation when a new bucket first receives observed time.
- Performance curve tests should cover ascending temperature ordering and exclusion of empty legacy buckets.
- Storage compatibility tests should cover restoring old fixed-range data with empty buckets and observed buckets, ensuring only observed buckets affect behavior.
- Existing calculator trend adjustment tests are prior art for parameterized calculator behavior. New calculator tests should follow that style for approximation and interpolation cases.
- Home Assistant config entry tests should use the existing Home Assistant testing patterns for setting up entries, states, services, and entity assertions.
- Good tests should use named temperatures that demonstrate the edge cases: below the old minimum, above the old maximum, negative fractional temperatures, positive fractional temperatures, dynamic service boundary values, and legacy empty buckets.

## Out of Scope

- Changing the definition of temperature operating zones for trend adjustment is out of scope.
- Adding configurable heating, neutral, or cooling thresholds is out of scope.
- Adding a new confidence value for distant forecast extrapolation is out of scope.
- Adding a separate extrapolation flag to forecast hour details is out of scope.
- Creating temperature buckets from hourly forecast data is out of scope.
- Creating temperature buckets from manual service requests is out of scope.
- Removing old empty bucket records from storage is out of scope.
- Changing weather forecast retrieval or forecast cache scheduling is out of scope.
- Changing scheduled forecast windows is out of scope.
- Changing translations beyond what is required for any new validation error text is out of scope.
- Reworking the broader entity model outside per-bucket dynamic creation is out of scope.

## Further Notes

The key domain distinction is that a temperature bucket is history, not a prediction artifact. Forecast and manual service temperatures are requested outdoor temperatures used to estimate forecast energy or manual energy, but they do not by themselves become bucket observations.

The dynamic service prediction range intentionally protects manual what-if usage from unbounded extrapolation while allowing natural forecast temperatures to be calculated. This keeps the user-facing service conservative without treating weather data as invalid.

The implementation should be careful around Home Assistant runtime entity creation. Dynamic bucket sensors should appear promptly, but repeated state updates for the same temperature bucket must not register duplicates.
