# Spec resolution (feature route, F3a)

The one procedure for turning a `{spec}` reference into a concrete spec file — here `{spec}` is the issue id. Shared contract: `om-auto-create-pr --spec` and `om-auto-implement-spec` follow this same order — update all consumers together.

Try in order; first hit wins:

1. **Issue reference guard** — first try **get-issue** when `{spec}` is an issue-shaped identifier under the configured tracker, not only when it is numeric. For the local-Markdown provider this includes `.scratch/.../issues/01-name.md` and feature-level `tickets.md`, but not an explicitly supplied `PRD.md` or a path under `$SPECS_DIR`. A successful lookup classifies the input as an issue: record `ISSUE_ID`, scan its body and comments for links/paths to `$SPECS_DIR` files or spec-PR references, and never use the issue file itself as the spec. A not-found result only means the input was not classified as an issue; continue below.
2. **Path** — only when step 1 did not resolve an issue, if `{spec}` is an existing repo-relative file path (under `$SPECS_DIR` or elsewhere), use it directly.
3. **Name/slug in `$SPECS_DIR`** — case-insensitive match of `{spec}` against filenames (with or without the `YYYY-MM-DD-` prefix and `.md`) and against each spec's `# {Title}` line. One match → use it. Multiple matches → pick the newest by filename date **only** when its title matches unambiguously; otherwise treat as not found and list the matches as candidates. Files under `$SPECS_DIR/capabilities/` are living capability specs (the Delta archive target), never change specs: exclude them from this match.
4. **Spec PR** — when issue lookup found a PR reference, or a numeric input was not an issue, **get-pr**: if the PR's branch adds a file under `$SPECS_DIR`, use that file and set `SPEC_PR`. Also run **search-prs** for open PRs referencing the resolved spec path — an open spec PR means the spec is in flight (set `SPEC_PR`; the spec PR stays design-only — implementation ships on its own PR referencing it).

Validate the resolved file: it must contain an `## Implementation Plan` (or `## Phasing`) section to be implementable. When it lacks one, stop with the not-found notification variant: "spec found but has no implementation breakdown — run om-spec-writing to complete it first."

## Not-found notification

```
Status: blocked
Spec not found for "{spec}".
Searched: tracker issue body/comments, path, $SPECS_DIR name/title match, spec-PR branches.
Closest candidates:
- {path} — {title}
- …
Next: pass an exact path, or create the spec first with om-auto-write-spec "{spec}".
```

## om-auto-fix-issue specifics

On this skill's feature route "not found" is not a stop: it routes to F3c — invoke `om-auto-write-spec {issueId}` to author the spec first, then chain `om-auto-implement-spec {SPEC_PATH}`.
