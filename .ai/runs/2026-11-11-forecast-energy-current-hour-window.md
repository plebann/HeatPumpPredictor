# Execution plan: current-hour Forecast Window selection

Source doc: `.ai/specs/briefs/2026-11-11-forecast-energy-current-hour-window.md`

## Goal

Make `starting_hour` select the complete local hourly Forecast Window that is currently in progress, while preserving the public response shape and selecting the active occurrence of a repeated DST hour.

## Scope

- Change Forecast Window selection in `ForecastEnergyCalculator` so the requested current local hour remains eligible until that hour ends.
- Seed Trend Adjustment for the current-hour window from `current_temperature`; omit the first adjustment when that reading is unavailable.
- Preserve correct instant ordering across timezone conversion and repeated DST hours.
- Add contract-level regression and boundary coverage, then update user and requirement documentation that describes the superseded selection rule.

## Non-goals

- Do not prorate energy for the elapsed part of the current hour.
- Do not add a full datetime input or change the service response schema.
- Do not redesign forecast parsing or Trend Adjustment outside the first current hour.
- Do not change Scheduled Forecast schedules or extend forecast energy accuracy behavior.

## Implementation Plan

### Phase 1: Correct the Forecast Window contract

1. Add calculator regression tests covering current-hour boundaries, current-temperature seeding and fallback, timezone conversion, and both DST transitions.
2. Implement instant-safe current-hour selection and Trend Adjustment seeding without changing later-window behavior or response fields.

### Phase 2: Document and verify the intentional behavior change

1. Update service and Forecast Window documentation to define `starting_hour` as a complete local hourly bucket and record the superseded future-only rule.

## Risks

- Python comparisons between aware datetimes sharing a timezone can compare repeated wall times without distinguishing `fold`; selection must compare absolute instants where ambiguity exists.
- Forecast providers may omit the current bucket or a spring-forward wall hour; the existing next-available/error behavior must remain deterministic.
- This intentionally changes a public service value while preserving its input and response shape, so contract tests and release-facing documentation are required.

## Progress

PR: #11

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Correct the Forecast Window contract

- [x] 1.1 Add calculator regression tests covering current-hour boundaries, current-temperature seeding and fallback, timezone conversion, and both DST transitions. — 49e5656
- [x] 1.2 Implement instant-safe current-hour selection and Trend Adjustment seeding without changing later-window behavior or response fields. — e4a66b9

### Phase 2: Document and verify the intentional behavior change

- [x] 2.1 Update service and Forecast Window documentation to define `starting_hour` as a complete local hourly bucket and record the superseded future-only rule. — 5e09261
