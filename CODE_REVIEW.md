# Code review

## Review priorities

Review in this order:

1. correctness of energy, time, temperature-bucket, and forecast calculations;
2. backward compatibility of Home Assistant services, entities, config entries,
   storage, and translations;
3. async safety and Home Assistant lifecycle behavior;
4. persistence and restart behavior;
5. focused tests at the deepest useful module boundary;
6. readability and consistency with repository conventions.

## Repository-specific checks

### Domain behavior

- Use the exact terminology in `CONTEXT.md` and preserve the distinctions
  between observations and predictions.
- Preserve Previous-State Attribution: elapsed time and energy belong to the
  prior Outdoor Temperature observation.
- Forecast and manual prediction requests must not create historical
  Temperature Buckets.
- Keep domain calculation modules independent from Home Assistant imports when
  an ADR establishes that boundary.
- Treat rounding, confidence values, approximation source, and response fields
  as behavior, not formatting details.

### Home Assistant integration

- Keep I/O asynchronous and never block the event loop.
- Preserve config-entry setup, unload, reload, and callback cleanup behavior.
- Use `DataUpdateCoordinator` and `CoordinatorEntity` consistently with the
  existing implementation.
- Entities need stable unique IDs, `_attr_has_entity_name = True`, and
  translation-backed names.
- Validate service inputs and map domain failures to existing translated
  `ServiceValidationError` contracts.
- Keep `manifest.json`, `strings.json`, `translations/`, and `services.yaml`
  synchronized when their shared contract changes.
- Do not add credentials, tokens, personal data, or sensitive state to logs,
  diagnostics, fixtures, or committed files.

### Persistence and compatibility

- Review changes to `Store` keys, `STORAGE_VERSION`, serialized bucket data,
  restored sensor attributes, and config-entry data as migrations.
- Existing stored data must either remain readable or have a tested migration.
- Empty legacy Temperature Buckets must not become observations accidentally.
- Entity unique IDs and service response keys are protected contracts; changes
  require the process in `BACKWARD_COMPATIBILITY.md`.

### Tests

- Run `.\venv\Scripts\python.exe -m pytest tests/ -v`.
- Require a regression test for behavior changes and bug fixes.
- Prefer tests through `ForecastEnergyCalculator`, calculator, data-manager, or
  sensor-builder seams over private helper assertions.
- Use explicit times and deterministic fakes; avoid wall-clock dependence.
- Cover negative and unavailable-state paths, not only the happy path.
- Do not report validation as passing when environment/plugin failures prevent
  the complete command from running.

## Finding severity

- **Blocker** — data loss, security issue, invalid persistence migration,
  broken public contract, incorrect energy attribution, or a change that cannot
  safely ship.
- **Major** — user-visible defect, important missing failure handling, lifecycle
  leak, meaningful untested behavior, or ADR violation.
- **Minor** — bounded maintainability or test-quality issue that should be
  addressed but does not invalidate the change.
- **Nit** — optional polish with no correctness or contract impact.

Approve only when there are no unresolved blocker or major findings and the
validation, compatibility, and applicable QA evidence are complete.
