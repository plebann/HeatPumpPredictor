# Implementation plan: forecast energy accuracy

Source doc: `.ai/specs/2026-11-07-forecast-energy-accuracy.md`
Spec PR: #7 (https://github.com/plebann/HeatPumpPredictor/pull/7)

## Goal

Persist successful public energy forecast calls, validate complete windows against the configured cumulative heat-pump energy sensor, and expose explainable energy-weighted accuracy diagnostics without changing the existing service response or temperature validation behavior.

## Scope

- Extend `ForecastValidationManager` with source-bound energy observations, Recorder boundary validation, retries, persistence, deduplication, pruning, and EWMA aggregation.
- Register only public service calls and preserve the existing dictionary response through an internal raw-result seam.
- Add the configurable half-life option and diagnostic sensor, translations, documentation, and regression tests.

Non-goals: removing Scheduled Forecast sensors, changing forecast calculation, changing the public service contract, automatic forecast correction, or historical backfill.

## Risks

- Store migration must preserve existing temperature validation records.
- Recorder boundary semantics and cumulative-counter resets can silently bias accuracy.
- Existing service consumers must continue receiving the exact dictionary response shape.

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Persist and verify energy forecast windows

- [x] 1.1 Characterize the existing service contract and add the internal raw-result seam — 208fcf8
- [x] 1.2 Add source-bound energy observation persistence, deduplication, migration, and pruning — 208fcf8
- [x] 1.3 Register successful public service calls without recording direct coordinator consumers — 208fcf8
- [x] 1.4 Implement Recorder boundary validation, retry, reset detection, and restart handling — 208fcf8
- [x] 1.5 Add phase-1 regression and integration-style tests — 208fcf8

### Phase 2: Aggregate and expose accuracy

- [x] 2.1 Implement chronological EWMA aggregation, buckets, recent average, and thresholds — 208fcf8
- [x] 2.2 Add half-life configuration and the translated diagnostic sensor — 208fcf8
- [ ] 2.3 Update documentation, run the full validation gate, and complete review fixes
