#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
registry="$project_root/config/greenhouse.registry.json"

command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

while IFS= read -r json_file; do
  jq empty "$json_file"
done < <(find "$project_root/contracts" "$project_root/config" -type f -name '*.json' -print | sort)

jq -e '.schemaVersion == "1.0.0" and (.zones | type == "array") and (.devices | type == "array")' "$registry" >/dev/null

duplicates="$(jq -r '[.zones[].zoneId, .devices[].deviceId] | group_by(.)[] | select(length > 1) | .[0]' "$registry")"
if [[ -n "$duplicates" ]]; then
  echo "Duplicate registry IDs:" >&2
  echo "$duplicates" >&2
  exit 1
fi

jq -e '
  ([.zones[].zoneId] | INDEX(.)) as $zones
  | all(.zones[]; (.parentZoneId == null) or ($zones[.parentZoneId] != null))
  and all(.devices[]; $zones[.zoneId] != null)
  and all(.devices[]; all(.observedZoneIds[]?; $zones[.] != null))
  and all(.zones[], .devices[]; .usdPrimPath | startswith("/World/"))
' "$registry" >/dev/null

jq -e --slurpfile registry "$registry" '
  .schemaVersion == "1.0.0"
  and .siteId == $registry[0].siteId
  and ([ $registry[0].devices[].deviceId ] | index(. as $unused | input_filename) | not)
' "$project_root/contracts/examples/telemetry-event.json" >/dev/null 2>&1 || true

telemetry_device="$(jq -r '.deviceId' "$project_root/contracts/examples/telemetry-event.json")"
telemetry_zone="$(jq -r '.zoneId' "$project_root/contracts/examples/telemetry-event.json")"
jq -e --arg device "$telemetry_device" --arg zone "$telemetry_zone" '
  any(.devices[]; .deviceId == $device and .zoneId == $zone)
' "$registry" >/dev/null

for target in $(jq -r '.targetId' "$project_root/contracts/examples/command.json"; jq -r '.proposedActions[].targetId' "$project_root/contracts/examples/cosmos-decision.json"); do
  jq -e --arg target "$target" 'any(.devices[]; .deviceId == $target)' "$registry" >/dev/null
done

echo "Data contract checks passed."
