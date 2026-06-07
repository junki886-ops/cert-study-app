#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"

echo "Pushing ${BRANCH} to GitHub origin..."
git push origin "${BRANCH}"

echo "Pushing ${BRANCH} to Hugging Face hf..."
git push hf "${BRANCH}"

echo "Done."
