#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dry}"
if [[ $# -gt 0 ]]; then
  shift
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
SCRIPT="tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py"

CATEGORIES=(
  table
  cabinet
  dresser
  stool
  fridge
  bathtub
  bench
  desk
  counter
  sink
  nightstand
  oven
  microwave
  dishwasher
  vase
)

COMMON_ARGS=(
  --scene-root "${SCENE_ROOT:-data/scene_datasets/hssd-hab}"
  --inventory-json "${INVENTORY_JSON:-docs/audits/hssd_category_expansion_inventory.json}"
  --output-dir "${OUTPUT_DIR:-outputs/hssd_fixed_camera_viewpoint_prototype}"
  --categories "${CATEGORIES[@]}"
  --seed "${SEED:-13}"
)

case "${MODE}" in
  dry)
    exec "${PYTHON_BIN}" "${SCRIPT}" \
      "${COMMON_ARGS[@]}" \
      --dry-run \
      --max-scenes "${MAX_SCENES:-3}" \
      --max-objects-per-category "${MAX_OBJECTS_PER_CATEGORY:-2}" \
      --samples-per-object "${SAMPLES_PER_OBJECT:-8}" \
      "$@"
    ;;
  small)
    exec "${PYTHON_BIN}" "${SCRIPT}" \
      "${COMMON_ARGS[@]}" \
      --max-scenes "${MAX_SCENES:-3}" \
      --max-objects-per-category "${MAX_OBJECTS_PER_CATEGORY:-2}" \
      --samples-per-object "${SAMPLES_PER_OBJECT:-12}" \
      "$@"
    ;;
  full)
    exec "${PYTHON_BIN}" "${SCRIPT}" \
      "${COMMON_ARGS[@]}" \
      --max-scenes "${MAX_SCENES:-0}" \
      --max-objects-per-category "${MAX_OBJECTS_PER_CATEGORY:-0}" \
      --samples-per-object "${SAMPLES_PER_OBJECT:-48}" \
      "$@"
    ;;
  *)
    echo "Usage: $0 {dry|small|full} [extra prototype args]" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  $0 dry" >&2
    echo "  $0 small --debug-images --max-debug-images 20" >&2
    echo "  MAX_SCENES=20 SAMPLES_PER_OBJECT=32 $0 full" >&2
    exit 2
    ;;
esac
