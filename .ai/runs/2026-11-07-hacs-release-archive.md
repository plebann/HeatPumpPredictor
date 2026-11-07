# Execution plan: include HACS metadata in release archives

- Goal: Ensure every release ZIP created by `.github/workflows/release.yml` contains the root `hacs.json` required by HACS, while preserving the existing integration archive layout.
- Source doc: `.ai/specs/briefs/2026-11-07-hacs-release-archive.md`
- Branch: `fix/hacs-release-archive`

## Scope

- Update the release archive step to include `hacs.json`.
- Add a packaging assertion that checks the generated ZIP contains `hacs.json` and the integration `manifest.json`.
- Run the repository validation command and inspect the workflow diff.

## Non-goals

- Do not alter integration runtime code or manifest version handling.
- Do not republish, retag, or modify the existing `v0.4.3` release.
- Do not change HACS metadata values or the release versioning policy.

## Risks

- A changed archive layout could break HACS installation; the archive check must preserve the current root-level integration files.
- GitHub Actions packaging behavior should be validated with a locally reproducible ZIP command where possible.

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Release packaging

- [x] 1.1 Include `hacs.json` in the release ZIP and add an archive-content guard — 859c6df
- [ ] 1.2 Run validation and review the final workflow diff
