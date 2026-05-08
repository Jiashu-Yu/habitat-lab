# HSSD Fixed-camera Viewpoint Prototype Plan

This document describes the first repo-native prototype for generating and auditing HSSD ObjectNav viewpoints under a fixed evaluation camera. It does not claim that fixed-camera viewpoints have already been generated.

## Motivation

The HSSD ObjectNav work is moving beyond the native six categories:

`bed`, `chair`, `couch`, `potted_plant`, `toilet`, `tv`

The first expansion candidates are:

`table`, `cabinet`, `dresser`, `stool`, `fridge`, `bathtub`, `bench`, `desk`, `counter`, `sink`, `nightstand`, `oven`, `microwave`, `dishwasher`, `vase`

For the target policy/evaluation setup, the action space does not include `look_up`, `look_down`, or any tilt action. Therefore, a viewpoint should only count as valid if the target is visible from the policy camera at the fixed pitch used for evaluation. Viewpoints that are only valid after an oracle tilt sweep are not equivalent.

## Files

- Prototype script: `tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py`
- Linux wrapper: `tools/hssd_viewpoint/run_fixed_camera_viewpoint_prototype.sh`
- Default output directory: `outputs/hssd_fixed_camera_viewpoint_prototype/`

Generated outputs are ignored by git via repo-root `.gitignore`.

## Modes

### Dry mode

Command:

```bash
bash tools/hssd_viewpoint/run_fixed_camera_viewpoint_prototype.sh dry
```

Behavior:

- Parses HSSD scene metadata and scene instance JSON.
- Selects target objects by category.
- Produces a candidate-position sampling plan.
- Does not import Habitat-Sim.
- Does not initialize a simulator.
- Does not render.
- Does not compute visibility.

This mode is safe for checking category/object selection on local machines without Habitat installed.

### Small mode

Command:

```bash
bash tools/hssd_viewpoint/run_fixed_camera_viewpoint_prototype.sh small
```

Behavior:

- Imports Habitat-Sim.
- Builds a simulator per scene.
- Samples a small number of candidate positions.
- Keeps camera pitch fixed.
- Renders RGB and semantic observations.
- Computes visible pixel count, image fraction, distance to object, and a simple mask coverage score.

This mode is intended for server smoke tests after Habitat is available.

### Full mode

Command:

```bash
bash tools/hssd_viewpoint/run_fixed_camera_viewpoint_prototype.sh full
```

Behavior:

- Same algorithm as small mode but with broader default scale.
- Environment variables can still cap scope:

```bash
MAX_SCENES=20 MAX_OBJECTS_PER_CATEGORY=10 SAMPLES_PER_OBJECT=32 \
  bash tools/hssd_viewpoint/run_fixed_camera_viewpoint_prototype.sh full
```

Full mode is still a prototype audit/generation pass, not a training job.

## Direct Python Usage

```bash
python tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py \
  --scene-root data/scene_datasets/hssd-hab \
  --inventory-json docs/audits/hssd_category_expansion_inventory.json \
  --output-dir outputs/hssd_fixed_camera_viewpoint_prototype \
  --categories table cabinet dresser stool fridge bathtub bench desk counter sink nightstand oven microwave dishwasher vase \
  --max-scenes 3 \
  --max-objects-per-category 2 \
  --samples-per-object 12 \
  --seed 13 \
  --dry-run
```

## Fixed-camera Assumptions

Default prototype camera/agent values are LoCoBot-like HSSD defaults:

- RGB/semantic resolution: `640 x 480`
- HFOV: `79`
- camera height: `0.88`
- camera pitch: `0.0` degrees
- agent height: `0.88`
- agent radius: `0.18`

These are command-line arguments because viewpoint validity is only meaningful relative to the camera/embodiment used for policy evaluation.

The prototype explicitly does not use:

- `look_up`
- `look_down`
- tilt sweeps
- oracle camera motion from STOP pose

## Algorithm Sketch

For each selected target object:

1. Resolve the object category from HSSD metadata.
2. Use the scene instance translation and metadata dimensions as a static object-center approximation.
3. In non-dry-run mode, initialize Habitat-Sim for the scene.
4. Match the static object record to a semantic-scene object by nearest semantic AABB center, with a category-name bonus when available.
5. Sample candidate positions around the object at multiple radii.
6. Snap candidate positions to the navmesh.
7. Set agent yaw to face the target center.
8. Keep camera pitch fixed.
9. Render RGB and semantic observations.
10. Count target semantic pixels.
11. Compute:
    - visible pixel count
    - image fraction
    - Euclidean distance to object
    - planar XZ distance to object
    - mask bounding box
    - mask fill/coverage score
12. Run threshold sweeps over visibility and distance.

## Threshold Sweep

The prototype records per-object pass/fail counts for:

- `min_visible_pixels`: `100`, `300`, `500`, `1000`
- `min_image_fraction`: `0.001`, `0.003`, `0.005`, `0.01`
- `max_distance`: `1.0`, `1.5`, `2.0`, `3.0`
- `min_viewpoints_per_object`: `1`, `3`, `5`

The sweep is intended to answer which thresholds are realistic before committing to a dataset regeneration policy.

## Outputs

The script writes:

- `output-dir/hssd_fixed_camera_viewpoint_prototype.json`
- `output-dir/hssd_fixed_camera_viewpoint_prototype.md`
- `output-dir/debug_images/` when `--debug-images` is enabled

Debug images are always placed below the selected output directory, never in the repo root.

## Current Limitations

- Dry-run mode does not prove navigability or visibility.
- Semantic object matching is a prototype nearest-AABB-center heuristic.
- `iou` is left as `null` because the prototype does not yet compute a projected full-object reference mask.
- `coverage_score` currently means target-mask fill inside the observed target-mask bounding box.
- Object center from static metadata is approximate and ignores object rotation.
- The script records candidate metrics; it does not yet write final Habitat ObjectNav `view_points` back into dataset shards.
- Manual visual spot checks are still required before using generated viewpoints for training/evaluation.

## What Would Count As A Successful Prototype Run

For a small server run:

- no scene-level crashes, or failures isolated in `failed_scenes`
- target categories resolve to expected HSSD objects
- debug RGB/mask pairs show the intended object
- several categories achieve at least 3 fixed-camera visible viewpoints per object under reasonable thresholds
- categories with poor fixed-camera visibility are identified before dataset regeneration

## Next Implementation Steps

1. Run dry mode locally to confirm category/object selection.
2. Run small mode on the server with `--debug-images`.
3. Manually inspect debug RGB/mask pairs for each category.
4. Tune thresholds for fixed-camera visibility.
5. Add a stronger semantic-object matching method if nearest AABB is unreliable.
6. Add final writer for ObjectNav-compatible `view_points` only after the visibility audit is trusted.
