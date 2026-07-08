# ADR-0001: Forecast Energy Module Seam

## Status

Accepted

## Context

`Forecast Energy` is currently calculated inside the Home Assistant coordinator. The coordinator parses the `Hourly Forecast`, selects the `Forecast Window`, derives the previous outdoor temperature for `Trend Adjustment`, calls the heat pump calculator, and shapes the response consumed by manual service calls and `Scheduled Forecast` sensors.

That makes the coordinator module shallow as an architecture seam: callers and tests must understand Home Assistant details to exercise the forecast calculation, while the forecast calculation itself has poor locality.

## Decision

Create a deep `ForecastEnergyCalculator` module for Forecast Energy calculation.

The coordinator remains the Home Assistant adapter. It owns forecast cache retrieval, current Home Assistant state lookup, and mapping domain forecast errors to Home Assistant validation errors.

The `ForecastEnergyCalculator` interface accepts the cached hourly forecast list, the forecast window request, the current outdoor temperature if available, and an explicit `now` value. It depends on a heat pump calculator supplied at construction time.

The module returns a typed domain result internally, with a serializer that preserves the current Home Assistant response dictionary fields and rounding.

Forecast calculation errors are represented by one domain exception carrying a reason key and placeholders. The coordinator maps those reason keys to existing Home Assistant translation keys.

## Consequences

Forecast Window selection, previous-temperature selection, Trend Adjustment orchestration, and Forecast Energy result construction gain locality in one module.

Tests can target the Forecast Energy seam directly without setting up Home Assistant.

The existing service and scheduled forecast response contract remains stable.

A separate `estimate_forecast_hour` calculator interface is deliberately deferred until a second caller or stronger reuse pressure proves that seam is real.
