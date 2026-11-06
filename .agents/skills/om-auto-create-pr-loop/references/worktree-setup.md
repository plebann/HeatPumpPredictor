# Worktree setup — isolated worktree and task branch

Detailed procedure for step 6 (create) and step 14 (cleanup) of `om-auto-create-pr-loop`. Never run in the user's primary worktree.

## Create the worktree and task branch (step 6)

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
GIT_DIR=$(git rev-parse --git-dir)
GIT_COMMON_DIR=$(git rev-parse --git-common-dir)
WORKTREE_PARENT="$REPO_ROOT/.ai/tmp/om-auto-create-pr-loop"
CREATED_WORKTREE=0
RUN_DIR_SOURCE=""

# Planned runs author PLAN/HANDOFF/NOTIFY before this setup. Remember the
# source folder so those uncommitted files cross into a newly created worktree.
# Simple runs intentionally have no run folder and leave this empty.
if [ -n "${RUN_DIR:-}" ] && [ -d "$REPO_ROOT/$RUN_DIR" ]; then
  RUN_DIR_SOURCE="$REPO_ROOT/$RUN_DIR"
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

if [ "$CREATED_WORKTREE" = "1" ] && [ -n "$RUN_DIR_SOURCE" ]; then
  mkdir -p "$RUN_DIR"
  cp -R "$RUN_DIR_SOURCE/." "$RUN_DIR/"
fi
```

Then install dependencies with whatever the repository's lockfile implies (npm, pnpm, bun, cargo, etc.); skip when the project needs no install step.

Rules:

- Reuse the current linked worktree when already inside one. Never nest worktrees.
- Never reset an existing task branch. Re-enter it through the resume workflow,
  or stop and let the operator decide which local progress is authoritative.
- For a Planned run, copy the complete newly authored run folder into a fresh
  worktree before step 7 stages it. Preserve Simple runs' no-folder behavior.
- The main worktree must stay untouched.
- Always clean up the temporary worktree at the end, but only if you created it this run.

## Cleanup sequence (steps 6 and 14)

Run in a `trap`/finally so crashes also clean up (registered at creation time, executed at run end):

```bash
cd "$REPO_ROOT"
if [ "$CREATED_WORKTREE" = "1" ]; then
  git worktree remove --force "$WORKTREE_DIR"
fi
git worktree prune
```
