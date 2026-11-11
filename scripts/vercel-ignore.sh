#!/usr/bin/env bash
# Vercel ignoreCommand contract: exit 0 = skip this build, exit 1 = build.
# Docs-only and chores commits must not consume Hobby deployment quota.
set -u

previous="${VERCEL_GIT_PREVIOUS_SHA:-}"
if [ -z "$previous" ]; then
  exit 1
fi

git cat-file -e "$previous^{commit}" 2>/dev/null || exit 1

if git diff --quiet "$previous" HEAD -- \
  . \
  ":(exclude)docs" \
  ":(exclude)*.md" \
  ":(exclude)llms.txt" \
  ":(exclude).github"; then
  echo "Only docs/metadata changed - skipping build"
  exit 0
fi

exit 1
