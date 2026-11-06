# Tracker provider: Local Markdown + GitHub

This repository tracks requirements and implementation issues as Markdown under
`.scratch/`; GitHub remains the code host for pull requests, reviews, and CI.
Issue operations below are local filesystem operations. Pull-request and CI
operations explicitly delegate to the committed companion descriptor
`.ai/trackers/github.md`.

## Prerequisites

- Run from the repository root in a checkout containing `.scratch/` and
  `docs/agents/issue-tracker.md`.
- Read and preserve `docs/agents/issue-tracker.md` and
  `docs/agents/triage-labels.md` before mutating an issue.
- `git` is required. GitHub-backed operations additionally require the
  prerequisites and **auth-check** from `.ai/trackers/github.md`.
- Cross-repository issue operations are unsupported and must fail explicitly.
  Cross-repository PR/CI operations follow `github.md`.

## Conventions

- A canonical issue id is its repository-relative Markdown path, for example
  `.scratch/forecast-energy-calculator/issues/01-create-seam.md`. A PRD or a
  feature-level `tickets.md` may also be addressed by its path.
- A numeric id resolves only against `.scratch/*/issues/<NN>-*.md`, comparing
  the zero-padded numeric prefix. It is accepted only when exactly one file
  matches; zero or multiple matches fail and list candidates. Never guess.
- New feature issues live at
  `.scratch/<feature-slug>/issues/<NN>-<issue-slug>.md`. `NN` is one greater
  than the highest existing prefix in that feature, starting at `01`.
- The first H1 is the title. `Status: <value>` near the top is the workflow
  state. Optional `Assignee:` and `Labels:` lines use comma-separated opaque
  strings. Existing front matter and prose must be preserved.
- Canonical local workflow values are `needs-triage`, `needs-info`,
  `ready-for-agent`, `ready-for-human`, and `wontfix`. `done` is the closed,
  completed state. Unknown values are preserved but reported.
- Comments append under one `## Comments` heading. Each comment starts with
  `### <comment-id>`, followed by `Author: <name>`, `Created: <ISO-8601 UTC>`,
  a blank line, then the body. A comment id is `comment-<UTC basic timestamp>`;
  add a numeric suffix on collision.
- A PR references a local issue with `Local-Issue: <canonical-path>` in its
  body. GitHub closing keywords do not close local files. After merge,
  **close-issue** must set `Status: done` and append the PR link.
- Drafts, PR comments, reviews, checks, and merges use GitHub semantics from
  the companion descriptor.
- Local claim signals are `Assignee: <current-user>`, `in-progress` in the
  `Labels:` line when labels are enabled, and a timestamped `🤖` claim comment.
  All are returned by **get-issue**. `ci-monitoring` is never a claim.
- Every write is narrow: update only the named metadata line, title, body, or
  comment. Preserve unrelated text and line endings. Read the file back after
  every mutation that gates later work.

## Label guards

- When `labels.enabled` is `false`, every issue and PR label operation is a
  logged no-op. This repository's initial pipeline configuration uses this
  mode.
- When labels are enabled, local issue labels are opaque comma-separated
  values in `Labels:`. The five canonical triage labels also set `Status:` to
  the same value. Removing a label does not infer a replacement status.
- For PR labels, use the existence guards from `.ai/trackers/github.md`.
- Never delete, rename, or recolor an existing GitHub label.

## Operations

### Identity and repository

#### auth-check

Verify `.scratch/`, `docs/agents/issue-tracker.md`, and
`.ai/trackers/github.md` exist, then execute **auth-check** from `github.md`.
Missing local paths or failed GitHub authentication fail the operation.

#### current-user

Execute **current-user** from `github.md`. If GitHub is unavailable for a
strictly local issue read, fall back to `git config user.name`; mutation and
claim operations still require the GitHub identity check.

#### repo-info / default-branch

Execute the identically named operation from `.ai/trackers/github.md`.

### Issues

#### get-issue

Resolve the id by the conventions above and read the complete file. Return an
object containing: canonical `id` and `url` (both the repo-relative path), H1
`title`, complete `body`, `state` (`CLOSED` for `done` or `wontfix`, otherwise
`OPEN`), raw `status`, parsed `labels`, parsed `assignees`, and parsed comments
including id, author, created timestamp, body, and local path anchor. Missing or
ambiguous ids fail and list candidates.

#### search-issues

Glob `.scratch/**/*.md`, excluding generated archives. Parse each candidate as
in **get-issue**. Filter case-insensitively against title and body. State
`open` excludes `done` and `wontfix`; `closed` includes them; `all` applies no
state filter. Return canonical path, title, status, and state. An empty query
enumerates the selected state. There is no pagination cap.

#### create-issue

Require a validated feature slug (`^[a-z0-9]+(?:-[a-z0-9]+)*$`), title, and
body. Create `.scratch/<feature>/issues/` if needed, allocate the next `NN`,
slugify the title, and create only a previously absent file with:

```markdown
# <title>

Status: needs-triage
Assignee: <assignee when supplied>
Labels: <labels when supplied>

<body>

## Comments
```

Do not overwrite. Return the canonical path as id and URL.

#### close-issue

Resolve and read the issue. Set `Status: done` for completed work or
`Status: wontfix` only when explicitly requested. Append the supplied closing
comment through **comment-issue**, including the merged/closed PR URL when one
exists. Read back and require `state: CLOSED`.

#### comment-issue

Resolve the issue, ensure exactly one `## Comments` heading (append one if
missing), generate a collision-free comment id, and append the structured
comment format from Conventions. Preserve multiline bodies verbatim. Return
`<canonical-path>#<comment-id>`.

#### update-issue

Resolve first. A title update replaces only the first H1. A body update
replaces prose after metadata and before `## Comments`, preserving H1,
`Status:`, `Assignee:`, `Labels:`, and all comments. Apply only supplied
fields, then read back.

#### assign-issue / unassign-issue

Resolve first. Add or update the single `Assignee:` metadata line near
`Status:`. Assignment preserves other comma-separated assignees and avoids
duplicates. Unassignment removes only the named user; retain an empty
`Assignee:` line when none remain. Read back the parsed assignees.

#### label-issue / unlabel-issue

Apply the Label guards above. When enabled, add/remove only the exact opaque
label in the comma-separated `Labels:` line. Adding a canonical triage label
also replaces `Status:` with that label. Read back labels and status.

#### get-issue-comment

Accept `<canonical-path>#<comment-id>`, resolve the issue, and return the
matching parsed comment. Missing or duplicate ids fail.

#### list-issue-comments

Resolve the issue and return every structured subsection under `## Comments`
in file order. Legacy unstructured text is returned once as a synthetic
read-only `legacy-comments` item and must not be discarded.

#### update-comment

Resolve `<canonical-path>#<comment-id>` and replace only that comment's body,
preserving its heading, author, and original created timestamp. The synthetic
`legacy-comments` item cannot be edited; append a superseding structured
comment instead. Read the comment back after mutation.

### Pull requests

All operations in this section execute the identically named operation from
`.ai/trackers/github.md`, including its validation, field shapes, guards, and
read-back rules:

- **get-pr**, **list-prs**, **search-prs**, **create-pr**, **update-pr**,
  **close-pr**, **comment-pr**, **attach-image-evidence**
- **assign-pr / unassign-pr**, **label-pr / unlabel-pr**
- **get-pr-diff**, **get-pr-files**, **get-pr-author-association**,
  **checkout-pr**, **review-pr**, **merge-pr**, **mark-pr-ready**
- **get-pr-checks**, **get-required-checks**, **get-pr-comment**,
  **get-review-comment**, **list-review-comments**

When creating or updating a PR for a local issue, include
`Local-Issue: <canonical-path>` and never emit a GitHub closing keyword for
that local path.

### CI runs

Execute **list-runs**, **get-run**, **get-run-failed-logs**,
**rerun-failed**, **approve-pending-runs**, and **watch-run** from
`.ai/trackers/github.md` without modification.

### Labels

#### list-labels

When labels are disabled, return the five canonical local status values and
note that mutations are disabled. When enabled, return their union with every
opaque value found in local `Labels:` lines and GitHub's **list-labels** result.

#### create-label

Local labels need no registry: accept a validated nonempty opaque string and
report it available. GitHub PR-label creation delegates to `github.md`, but
only when labels are enabled and the caller explicitly targets PR labels.

#### ensure-label-taxonomy

When labels are disabled, report a no-op. When enabled, preserve the local
five-status vocabulary and delegate creation of missing PR labels to
`github.md`; never write the Open Mercato taxonomy into local issue files merely
to register it.
