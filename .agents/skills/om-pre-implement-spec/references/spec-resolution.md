# Spec resolution (step 1)

How `om-pre-implement-spec` turns a `{spec}` reference into exactly one spec file. The order matches the spec lookup `om-auto-implement-spec` uses, so an audit and the implementation that follows it resolve the same file.

Try in order; first hit wins:

1. **Issue reference guard** — first try **get-issue** when `{spec}` is an issue-shaped identifier under the configured tracker. For the local-Markdown provider this includes `.scratch/.../issues/01-name.md` and feature-level `tickets.md`, but not an explicitly supplied `PRD.md` or a path under `$SPECS_DIR`. A successful lookup records `ISSUE_ID`, scans body/comments for spec paths or spec-PR references, and prevents the issue Markdown itself from being treated as a spec. A not-found result only means the input was not classified as an issue.
2. **Path** — only when step 1 did not resolve an issue, if `{spec}` is an existing repo-relative file (under `$SPECS_DIR` or elsewhere; path-safety rules in `references/agentic-setup.md`), use it directly.
3. **Name/slug in `$SPECS_DIR`** — case-insensitive match of `{spec}` against filenames (with or without the `YYYY-MM-DD-` prefix and `.md`, subdirectories included) and against each spec's `# {Title}` line. One match → use it. Several → pick the newest by filename date **only** when its title matches unambiguously; otherwise they are candidates. Files under `$SPECS_DIR/capabilities/` are living capability specs (the Delta archive target), never change specs: exclude them from this match.
4. **Spec PR** — when issue lookup found a PR reference, or a numeric input was not an issue, use **get-pr** + **get-pr-files**; when the PR adds or changes a file under `$SPECS_DIR`, audit that file as it stands on the PR head and record `SPEC_PR`. Also run **search-prs** for open PRs referencing the resolved path — an open spec PR means the spec is still in flight; audit its head, not the base copy.

When the spec exists only on a PR branch, read it from the PR head without checking the branch out into the user's working tree (a read of the file at that ref is enough).

## Candidates and not-found

- **Several candidates** → interactive: list them (path — title) and ask which one; `--autonomous`: stop with the notification below, candidates listed.
- **Nothing found** → stop with the notification below. Never guess a spec or draft one — authoring is the `om-spec-writing` skill's job.

```
Status: blocked
Spec not found for "{spec}".
Searched: tracker issue body/comments, path, $SPECS_DIR name/title match, spec-PR branches.
Closest candidates:
- {path} — {title}
- …
Next: pass an exact path, or write the spec first with om-spec-writing.
Readiness: no-go
```

A spec that resolves but has no implementation breakdown (`## Implementation Plan` or `## Phasing`) is **not** a resolution failure — audit it; the readiness gate records the missing breakdown as a Critical gap.
