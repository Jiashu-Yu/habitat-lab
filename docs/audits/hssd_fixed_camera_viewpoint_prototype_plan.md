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
- Static output analyzer: `tools/hssd_viewpoint/analyze_fixed_camera_viewpoint_output.py`
- Static candidate selector: `tools/hssd_viewpoint/select_fixed_camera_viewpoints.py`
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
3. In non-dry-run mode, initialize Habitat-Sim for the scene with `enable_physics=True` so HSSD rigid objects are available.
4. Resolve the target scene-instance object to a runtime rigid object handle using `template_name`; when multiple handles match the same template, select the nearest runtime center/translation to the static target center.
5. Temporarily assign a high sentinel semantic ID to the selected rigid object and restore the original semantic ID after processing the object.
6. Match the static object record to a semantic-scene object by nearest semantic AABB center, with a category-name bonus when available, only for heuristic diagnostics.
7. Sample candidate positions around the object at multiple radii.
8. Snap candidate positions to the navmesh.
9. Set agent yaw to face the target center.
   The yaw quaternion is force-normalized before assigning `AgentState.rotation`; invalid or near-zero quaternions fall back to identity.
10. Keep camera pitch fixed.
11. Render RGB and semantic observations.
12. Count target semantic pixels using only the sentinel semantic ID. Heuristic semantic IDs are retained under `heuristic_*` fields but do not drive final `visible_pixels` or threshold sweep.
13. Compute:
    - semantic observation diagnostics: dtype, min, max, unique sample, and shape
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

Debug images are always placed below the selected output directory, never in the repo root. Each saved candidate writes an RGB image, a binary sentinel mask, an RGB+mask overlay image, and an annotated review image. The review image includes target metadata plus brightened RGB/overlay panels for dark HSSD assets.

## JSON Structure

The output JSON is intentionally structured for later analysis scripts:

- top-level result key: `object_results`
- per-object metadata key: `object`
- per-object candidate list key: `candidate_results`
- scene initialization/load failures: `failed_scenes`
- per-object processing failures: `failed_objects`
- candidate-level failures: `candidate_results[*].candidate_error` and `candidate_results[*].rejection_reason`

Each non-dry-run object result may include:

- `semantic_scene_diagnostics`
- `semantic_match`
- `semantic_mapping`
- `semantic_mapping_status`
- `sentinel_status`
- `original_rigid_semantic_id`
- `sentinel_semantic_id`
- `semantic_ids_checked`
- `candidate_semantic_id_diagnostics`, including raw IDs, filtered IDs, source labels, removed invalid IDs, and heuristic IDs
- `threshold_sweep`

Each rendered candidate result may include:

- `rotation_diagnostics`, including `rotation_norm_before`, `rotation_norm_after`, and whether normalization/fallback occurred
- `semantic_observation_diagnostics`, including `semantic_sensor_dtype`, `semantic_min`, `semantic_max`, `semantic_unique_sample`, and `semantic_unique_count`
- `semantic_mapping_status`
- `rigid_object_handle`
- `sentinel_semantic_id`
- `sentinel_visible_pixels`
- `sentinel_bbox`
- `sentinel_bbox_area_fraction`
- `sentinel_image_fraction`
- `sentinel_total_pixels`
- `sentinel_image_shape`
- `sentinel_mask_quality_flags`
- `heuristic_raw_candidate_semantic_ids`
- `heuristic_candidate_semantic_ids`
- `heuristic_best_semantic_id`
- `heuristic_visible_pixels`
- `pixel_counts_by_semantic_id`
- `best_semantic_id`
- `visible_pixels` / `visible_pixel_count`

`sentinel_mask_quality_flags` marks review cases such as `full_frame_sentinel_mask`, `near_full_frame_bbox`, `very_large_sentinel_mask`, and `tiny_sentinel_mask`. These flags are diagnostics for camera/object geometry and threshold tuning; they do not automatically reject candidates.

## Current Limitations

- Dry-run mode does not prove navigability or visibility.
- Rigid-object handle matching is still a prototype resolver. It has been smoke-tested on representative cases, but broad-scene ambiguity checks are still needed.
- Semantic object matching is kept only as a heuristic diagnostic. If `sim.semantic_scene.objects` is empty, the prototype can still use HSSD rigid object sentinel masks.
- Candidate semantic ID fallbacks can include IDs that are not the target. ID `0` is excluded from heuristic diagnostics, and non-zero heuristic IDs do not drive final `visible_pixels`.
- `iou` is left as `null` because the prototype does not yet compute a projected full-object reference mask.
- `coverage_score` currently means target-mask fill inside the observed target-mask bounding box.
- Object center from static metadata is approximate and ignores object rotation.
- The script records candidate metrics; it does not yet write final Habitat ObjectNav `view_points` back into dataset shards.
- Manual visual spot checks are still required before using generated viewpoints for training/evaluation.

## What Would Count As A Successful Prototype Run

For a small server run:

- no scene-level crashes, or failures isolated in `failed_scenes`
- target categories resolve to expected HSSD objects
- debug RGB/mask/overlay/review images show the intended object
- several categories achieve at least 3 fixed-camera visible viewpoints per object under reasonable thresholds
- categories with poor fixed-camera visibility are identified before dataset regeneration

## Next Implementation Steps

1. Run dry mode locally to confirm category/object selection.
2. Run small mode on the server with `--debug-images`.
3. Manually inspect debug review images for flagged cases and spot-check RGB/mask/overlay images for each category.
4. Confirm sentinel-based positives match debug RGB/mask images on the server.
5. Audit unresolved or ambiguous rigid-object mappings across the selected categories.
6. Tune thresholds for fixed-camera visibility.
7. Add a stronger rigid-object matching method if template+nearest-center is unreliable.
8. Add final writer for ObjectNav-compatible `view_points` only after the visibility audit is trusted.

After a small/full run, summarize the current JSON schema with:

```bash
python tools/hssd_viewpoint/analyze_fixed_camera_viewpoint_output.py \
  --input-json outputs/hssd_fixed_camera_viewpoint_prototype/hssd_fixed_camera_viewpoint_prototype.json \
  --output-dir outputs/hssd_fixed_camera_viewpoint_analysis
```

After manual review has established filtering rules, select high-quality candidate viewpoints with:

```bash
python tools/hssd_viewpoint/select_fixed_camera_viewpoints.py \
  --input-json outputs/hssd_fixed_camera_viewpoint_prototype/hssd_fixed_camera_viewpoint_prototype.json \
  --output-dir outputs/hssd_fixed_camera_viewpoint_selection \
  --min-viewpoints-per-object 3
```

Default selector policy based on the first manual review:

- reject `full_frame_sentinel_mask`
- reject `near_full_frame_bbox`
- reject `tiny_sentinel_mask`
- keep `very_large_sentinel_mask` as manual-review, not accepted by default
- require at least 1,000 visible pixels, 0.005 image fraction, and distance <= 3.0 m for accepted candidates

For targeted retries on specific difficult instances, use `--scene-ids` and `--instance-indices` to avoid rerunning unrelated objects:

```bash
python tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py \
  --scene-root data/scene_datasets/hssd-hab \
  --inventory-json docs/audits/hssd_category_expansion_inventory.json \
  --output-dir outputs/hssd_fixed_camera_viewpoint_retry_cabinet_fridge \
  --categories cabinet fridge \
  --scene-ids 102343992 \
  --instance-indices 27 140 \
  --max-scenes 0 \
  --max-objects-per-category 0 \
  --samples-per-object 32 \
  --candidate-radii 1.25 1.5 1.75 2.0 2.5 3.0 \
  --debug-images \
  --max-debug-images 600
```
