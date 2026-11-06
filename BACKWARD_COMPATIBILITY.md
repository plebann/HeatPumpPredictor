# Backward compatibility

## Policy

Heat Pump Predictor is installed through HACS and runs inside Home Assistant.
Existing config entries, automations, dashboards, entity registries, stored
observations, and service consumers are protected contracts. A refactor must
preserve these surfaces unless the change explicitly includes a migration and
release communication.

## Protected contract surfaces

### Integration identity and configuration

- Domain `heat_pump_predictor` and config-flow setup are stable.
- Existing config-entry keys and option semantics must remain readable.
- Removing or renaming an input requires a migration that preserves existing
  entries and a documented transition.

### Services

The registered services `calculate_energy` and `calculate_forecast_energy`,
their input fields, validation behavior, and response dictionaries are public.
Breaking changes include removing or renaming fields, changing units or value
types, changing rounding, narrowing accepted requests without an intentional
policy decision, or changing error translation semantics.

Additive optional fields are preferred. A breaking service change requires a
deprecation period when practical, updated `services.yaml` and translations,
consumer-facing release notes, and contract tests.

### Entities and registry identity

Entity unique IDs, config-entry association, device information, translation
keys, native units, device classes, state classes, default-enabled behavior,
and restored state/attributes are protected. Renaming a Python class is not a
breaking change by itself; changing the resulting Home Assistant identity is.

When an identity must change, provide an entity-registry migration or preserve
the old unique ID. Never silently create duplicate entities after upgrade.

### State and attribute shapes

Power Curve, Duty Cycle Curve, Energy Distribution, Hourly Forecast cache, and
Scheduled Forecast states and attributes may be consumed by dashboards and
automations. Field names, units, value types, confidence vocabulary,
approximation metadata, and datetime representation are stable contracts.

Add fields compatibly. Removing, renaming, or changing meaning requires a
migration plan, release notes, and tests covering an existing consumer shape.

### Persistence

Home Assistant `Store` data keyed by the integration and config entry is a
durable contract. `STORAGE_VERSION`, serialized Temperature Buckets, previous
tracking state, and restored forecast values must remain readable across an
upgrade.

Schema changes require:

1. an explicit version increase when the serialized shape changes;
2. a deterministic migration from every supported prior version;
3. tests with representative legacy data;
4. no conversion of empty legacy buckets into observed data;
5. safe failure behavior that does not overwrite recoverable old data.

### Domain semantics

The following are behavior contracts unless superseded by a PRD and ADR:

- Previous-State Attribution;
- floor-based Temperature Bucket identity;
- separation of observations from forecasts/manual predictions;
- Service Prediction Range behavior;
- Trend Adjustment zones and direction;
- Prediction Confidence vocabulary and Approximation Source semantics;
- Forecast Energy response fields and rounding.

Refactors must characterize these behaviors before changing their owners or
module boundaries.

### HACS and release artifacts

`manifest.json`, HACS metadata, repository layout under
`custom_components/heat_pump_predictor/`, translations, icons, and the release
ZIP layout are installation contracts. A release must remain installable over
an existing HACS installation without manual file cleanup.

## Required path for a breaking change

1. Identify affected consumers and stored data in the PRD/specification.
2. Prefer an additive compatibility layer or deprecation over immediate
   removal.
3. Add characterization tests for the old contract before implementation.
4. Implement and test migrations where persisted/config/entity identity is
   affected.
5. Update README, service metadata, translations, and release notes together.
6. Call out the break and rollback path in the pull request.
7. Obtain maintainer approval and independent review; user-facing changes also
   pass the configured QA gate.

An undocumented breaking change is a blocker in code review.
