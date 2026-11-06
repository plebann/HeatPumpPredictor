# Worktree setup — isolated worktree and task branch

Detailed procedure for step 5 (create) and step 13 (cleanup) of `om-auto-create-pr`. Never run in the user's primary worktree.

## Create the worktree and task branch (step 5)

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
GIT_DIR=$(git rev-parse --git-dir)
GIT_COMMON_DIR=$(git rev-parse --git-common-dir)
WORKTREE_PARENT="$REPO_ROOT/.ai/tmp/om-auto-create-pr"
CREATED_WORKTREE=0
PLAN_SOURCE=""

# Step 4 writes the plan before this setup runs. Keep its absolute source path
# so a fresh worktree can receive that uncommitted file after branch creation.
if [ -n "${PLAN_PATH:-}" ] && [ -f "$REPO_ROOT/$PLAN_PATH" ]; then
  PLAN_SOURCE="$REPO_ROOT/$PLAN_PATH"
fi

if [ "$GIT_DIR" != "$GIT_COMMON_DIR" ]; then
  WORKTREE_DIR="$PWD"
else
  WORKTREE_DIR="$WORKTREE_PARENT/${SLUG}-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$WORKTREE_PARENT"
  git fetch origin "$BASE_BRANCH"
  git worktree add --detach "$WORKTREE_DIR" "origin/$BASE_BRANCH"
  CREATED_WORKTREE=1
fi

cd "$WORKTREE_DIR"
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "$BRANCH" ]; then
  : # explicit re-entry in the branch's existing linked worktree
elif git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "Task branch '$BRANCH' already exists. Resume it explicitly; refusing to reset or overwrite local progress." >&2
  exit 1
else
  git switch -c "$BRANCH" "origin/$BASE_BRANCH"
fi

if [ "$CREATED_WORKTREE" = "1" ] && [ -n "$PLAN_SOURCE" ]; then
  mkdir -p "$(dirname "$PLAN_PATH")"
  cp "$PLAN_SOURCE" "$PLAN_PATH"
fi
```

Then install dependencies with whatever the repository's lockfile implies (npm, pnpm, bun, cargo, etc.); skip when the project needs no install step.

Rules:

- Reuse the current linked worktree when already inside one. Never nest worktrees.
- Never reset an existing task branch. Re-enter it through the resume workflow,
  or stop and let the operator decide which local progress is authoritative.
- When this run creates a fresh worktree, copy the plan authored by step 4 into
  it before step 6 stages the plan. Do not copy unrelated uncommitted files.
- The main worktree must stay untouched.
- Always clean up the temporary worktree at the end, but only if you created it this run.

## Cleanup sequence (steps 5 and 13)

Run in a `trap`/finally so crashes also clean up:

```bash
cd "$REPO_ROOT"
if [ "$CREATED_WORKTREE" = "1" ]; then
  git worktree remove --force "$WORKTREE_DIR"
fi
git worktree prune
```
