#!/bin/bash
# ============================================================
# Git-Lock Gate — refuses to build uncommitted scripts
# Ensures every voice generation is traceable to a commit.
# ============================================================
SCRIPT_MD="$1"

# Check git repo
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "  ⚠️  Not a git repo — skipping lock check"
    exit 0
fi

# Check if script is tracked and unmodified
if git ls-files --error-unmatch "$SCRIPT_MD" >/dev/null 2>&1; then
    if ! git diff --quiet HEAD -- "$SCRIPT_MD"; then
        echo ""
        echo "🛑 GIT-LOCK GATE: FAILED"
        echo "   Script has uncommitted changes: $SCRIPT_MD"
        echo "   Commit before building to lock the script hash."
        echo "   This prevents credits from being burned on re-edits."
        echo ""
        exit 1
    fi
    COMMIT=$(git log -1 --format="%h %s" -- "$SCRIPT_MD")
    echo "  🔒 Git-locked: $COMMIT"
else
    # New file — not yet tracked. Warn but allow.
    echo "  ⚠️  Script not tracked by git — build allowed but consider committing first"
fi
