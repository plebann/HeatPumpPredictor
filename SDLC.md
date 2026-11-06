# Software delivery process

## Purpose

This document describes how work moves from a local Markdown ticket to a
reviewed pull request in Heat Pump Predictor. The executable configuration is
`.ai/agentic.config.json`. New pull requests target `main`.

Requirements and implementation tickets live under `.scratch/`; pull requests,
reviews, and CI live on GitHub. The hybrid contract is defined in
`.ai/trackers/local-markdown.md`.

## Sources of truth

- Product and domain language: `CONTEXT.md`.
- Architectural decisions: `docs/adr/`.
- Local issue conventions: `docs/agents/issue-tracker.md`.
- Triage vocabulary: `docs/agents/triage-labels.md`.
- Feature specifications and PRDs: `.scratch/<feature-slug>/PRD.md`.
- Open Mercato working specifications: `.ai/specs/`.
- Validation gate: `.ai/agentic.config.json`.

## Roles

- **Author** — claims and implements the work, adds tests, and leaves a complete
  handoff or pull request.
- **Reviewer** — checks correctness, Home Assistant conventions, security, and
  protected contracts using `CODE_REVIEW.md`.
- **QA reviewer** — exercises user-facing Home Assistant behavior and records
  evidence for the exact tested commit.
- **Maintainer** — owns this process, pipeline configuration, releases, and
  exceptions to compatibility or QA rules.

## Lifecycle

| Stage | Done when |
|---|---|
| Discovery | The problem is understood and routed to no action, a local ticket, a specification, or direct bounded work. |
| Intake | A PRD or issue exists under `.scratch/` and states the desired outcome and acceptance criteria. |
| Triage | The issue is actionable on `main`, not already solved, and not claimed by another run. |
| Claim | The local issue records the assignee and a timestamped `🤖` claim comment. Labels are disabled, so no label is treated as a lock. |
| Design | User-facing behavior, failure states, service response effects, and compatibility constraints are decided before implementation. |
| Implement | The smallest coherent change and regression tests are complete. |
| Validate | `.\venv\Scripts\python.exe -m pytest tests/ -v` exits successfully. |
| Review | Findings from `CODE_REVIEW.md` are resolved and the current head is approved. |
| QA | User-facing work is exercised against a running Home Assistant environment and evidence is tied to the tested commit. |
| Merge | A human performs or authorizes the final squash merge after review, QA, and CI are green. Automerge is not enabled. |
| Reconcile | The local issue is set to `Status: done` and receives the merged PR link. |

## Local ticket states

Use the vocabulary defined in `docs/agents/triage-labels.md`:

- `needs-triage`
- `needs-info`
- `ready-for-agent`
- `ready-for-human`
- `wontfix`
- `done` for completed work

The state is stored as `Status: <value>` near the top of the Markdown issue.
GitHub closing keywords do not close local issues; reconciliation is an
explicit post-merge step.

## Claim protocol

Before changing an issue or its implementation, an agent:

1. reads the current issue and searches open PRs for its `Local-Issue:` path;
2. stops when another live claim or open implementation already covers it;
3. records itself in `Assignee:` without removing another assignee;
4. appends a timestamped `🤖` claim comment describing the run;
5. reads the issue back before starting work.

The claim is released on success or failure. A stale claim may be cleared only
after the maintainer verifies that no active run still owns it.

## Review and QA gates

Every change receives code review. Changes to Home Assistant service schemas,
entity identity, config flow, storage, translations, or persisted attributes
are protected contracts and must follow `BACKWARD_COMPATIBILITY.md`.

The QA gate is enabled. User-facing behavior must be exercised in Home
Assistant, including relevant unavailable/error states. Browser automation may
use the committed `agent-browser` descriptor, but repository-native tests and
human judgment remain authoritative. Evidence must name the scenario,
environment, result, limitations, and tested head SHA.

Because pipeline labels are disabled, approval is recorded in the PR review
and QA evidence rather than inferred from labels. No skill may merge merely
because a label is absent.

## Validation gate

Run the complete gate before review and again after material review fixes:

- `.\venv\Scripts\python.exe -m pytest tests/ -v`

Any non-zero exit blocks delivery. If a local environment limitation prevents
the command from running, report the exact limitation; do not call the gate
green.

## Pull requests and merge

- Target `main` unless an existing PR has another base branch.
- Include `Local-Issue: <repo-relative-path>` when work originates in
  `.scratch/`.
- Preserve the public Home Assistant and HACS contracts documented in
  `BACKWARD_COMPATIBILITY.md`.
- Keep automerge disabled. The configured mode is prepare-only and requires
  independent review and human QA if labels are enabled in the future.
- Squash merge only after validation, review, QA when applicable, and required
  GitHub checks pass.

## Amending this process

Change this document and `.ai/agentic.config.json` together. Re-run
`om-setup-agent-pipeline` when validation, tracker, browser, or delivery policy
changes. Product discovery can be added separately with
`om-setup-discovery-pipeline`.
