# Per-Step loop (lean, no per-Step chatter)

The per-Step half of step 8. A Step is atomic: one Step = one code commit,
followed by one plan-metadata commit that records the finalized code commit.

1. **Implement** only the work described by the Step. Never pull work forward from later Steps.
2. **Tests** — add or update tests for anything that changed behavior:
   - Unit tests are mandatory for any code change.
   - Escalate to integration tests for risky flows, permission checks, data scoping, workflows, or behavior that crosses component boundaries.
3. **Quick sanity check** — run the minimum needed to confirm the Step compiles and its own new tests pass (the typecheck and test commands from `validation.commands`, scoped to the affected package or test file when the toolchain supports scoping). Do NOT record these runs anywhere — they are scratch.
4. Re-read the diff and remove scope creep.
5. Re-check changed production files against the project's data-access and security conventions from its agent instructions (for example mandated repository/query helpers, scoping wrappers, or encryption-aware accessors).
6. **Commit the Step's code** with a clear conventional-commit subject. Example subjects:
   - `feat(ui): add confirmation dialog primitive`
   - `test(ui): cover confirmation dialog focus trap`
7. **Record the finalized commit without rewriting it.** Capture
   `STEP_SHA=$(git rev-parse --short HEAD)`, then in `PLAN.md`'s `## Tasks`
   table flip only this Step's `Status` from `todo` to `done` and set `Commit`
   to `$STEP_SHA`. Commit that metadata separately as
   `docs(runs): record Step <X.Y> completion`. The recorded SHA now remains an
   ancestor of the pushed head and can pass resume reachability checks. Never
   amend or fix up the code commit to make it contain its own identity.
8. **Push** both commits after every Step so `om-auto-continue-pr-loop` always has the latest state on the remote.
   - **Step review (`engine.stepReview: per-step` only)** — after the push, review this Step's commit range per `references/step-review.md` before starting the next Step.
9. **Do NOT** write a `step-<X.Y>-checks.md`. **Do NOT** rewrite `HANDOFF.md`. **Do NOT** append to `NOTIFY.md`, unless the Step produced a blocker, a scope decision worth recording, or a subagent delegation. Routine progress is inferred from the Tasks table and the commit log.
