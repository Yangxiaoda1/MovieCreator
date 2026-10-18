#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SECRET_FILE="${AIMOVIE_SECRET_FILE:-$ROOT/.secrets/aimovie_api.env}"

if [[ ! -f "$SECRET_FILE" ]]; then
  echo "Missing credential file: $SECRET_FILE" >&2
  return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
source "$SECRET_FILE"

required=(
  AIMOVIE_IMAGE_APP_ID
  AIMOVIE_IMAGE_APP_KEY
  ELEVENLABS_APP_ID
  ELEVENLABS_APP_KEY
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Credential variable is empty: $name" >&2
    return 1 2>/dev/null || exit 1
  fi
done

echo "AI Movie API environment loaded from $SECRET_FILE"

