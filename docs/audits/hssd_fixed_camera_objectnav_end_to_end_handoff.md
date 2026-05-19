# HSSD Fixed-Camera ObjectNav End-to-End Handoff

Date: 2026-05-16

Latest update, 2026-05-18: Jing's `hssd-viewpoint-yawfix` reference branch
was fetched from `jingz6676/ObjectNavigationRendering` and the Stage 1-3
viewpoint files were synced into this repo. The key change is the yaw fix
`atan2(-view_dir.x, -view_dir.z)`, plus V3-style selection gates and richer
Stage 3 QA rendering. See `docs/FIXED_CAMERA_PIPELINE_SUMMARY.md` for Jing's
iteration log and final recommended config.

Planning update, 2026-05-19: the next design pass should focus on category
source and threshold simplification. Category grounding should use official
`hssd-hab/metadata/hssd_obj_semantics_condensed.csv` columns 3 and 4:
`condensed_category` as the default canonical grouping label, and
`primary_semantic_category` as the fine-grained corrected label. Keep both, and
introduce/verify an explicit `task_category` mapping before training export.
Threshold experiments should compare per-category, unified, and tiny-vs-regular
profiles. Tilt remains out of scope unless the real robot can tilt. If the
rendered data moves to `256x256`, scale absolute pixel gates or prefer
fraction-based gates.

Latest code update, 2026-05-19: Jing pushed WIP rendering branch
`refactor/repo-cleanup-and-dual-tier` at commit `04e3f85`. It restructures the
rendering repo into `viewpoints/`, `episodes/`, `render/`, `postprocess/`,
`lib/`, and `ops/`, adds `viewpoints/_object_label_schema.py`, and introduces a
dual-tier label resolver:

- `navobj6_*`: strict HSSD ObjectNav-6 label using v0.2.5 white-list,
  WordNet synset mapping, and limited condensed+room fallback.
- `open_vocab`: always-populated language metadata from wnsynset, WordNet,
  FloorPlanner tags, and raw object names.

This supersedes treating `condensed_category` alone as the final task label.
The branch is not finished yet; in commit `04e3f85`, the wrapper's Stage 4
command still appears to use stale flags relative to the current parser.

For the research logic and train/eval data contract, see:

```text
docs/audits/hssd_fixed_camera_research_logic_data_spec_memo.md
```

For the Maxwell server migration plan, see:

```text
docs/audits/hssd_maxwell_migration_runbook.md
```

For a complete fresh-server/HPC runbook that connects this viewpoint pipeline
to `MP4 + Parquet` rendering, see the companion rendering repository:

```text
ObjectNavigationRendering/README_FIXED_CAMERA_HSSD.md
```

This document explains the full workflow behind the HSSD fixed-camera ObjectNav
viewpoint generator and how it connects to downstream `MP4 + Parquet` training
data generation in `ObjectNavigationRendering`.

Generated data is intentionally not committed. The intended handoff is code,
commands, and quality-control logic so the pipeline can be rerun on server/HPC
after rendering parameters are finalized.

## Research Position

The project started from comparing native HSSD ObjectNav with OVON. The key
conclusion was that the problem is not only `success_distance`. The real goal is
to determine whether HSSD can be turned into a scalable, controllable,
semantically reliable synthetic ObjectNav environment for OVON-style trajectory
data.

The current design separates three concerns:

| Layer | Question | Current artifact |
|---|---|---|
| Object semantics | Can we identify the target instance? | HSSD metadata inventory, runtime rigid-object matching, sentinel semantic id |
| Viewpoint quality | Is the target visible under the fixed camera? | prototype JSON, selection JSON/CSV, debug images, BEV QA maps |
| Training data | Can viewpoints become navigation trajectories? | HSSD ObjectNav split, MP4 shards, episode parquet, step parquet |

Official Habitat/HSSD and OVON both use goal `view_points` as ObjectNav success
anchors. We keep that semantics, but only high-quality fixed-camera viewpoints
are allowed into the generated v1 split.

## Important HSSD Findings

- The ObjectNav-compatible path is regular `scenes`, not `scenes-articulated`.
- Regular scenes can print:

  ```text
  The active scene does not contain semantic annotations : activeSemanticSceneID_ = 0
  ```

  This means Habitat-Sim does not expose populated object-level semantic scene
  annotations for this path. It does not mean object metadata is absent.

- The prototype therefore uses sentinel masks:
  1. map target metadata object to a runtime rigid object;
  2. temporarily assign sentinel semantic id `90000`;
  3. render semantic observation;
  4. count pixels equal to the sentinel id;
  5. restore the object's original semantic id.

- Category matching is alias-aware. A query category can match condensed,
  primary, main, clean, or super category fields. This matters for cases such as
  `chair` vs `seat`, `vase` vs decor/stand, and broad `cabinet` subclasses.

## Main Viewpoint Tools

```text
tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py
tools/hssd_viewpoint/select_fixed_camera_viewpoints.py
tools/hssd_viewpoint/build_fixed_camera_visual_qa_pack.py
tools/hssd_viewpoint/merge_fixed_camera_viewpoint_selections.py
tools/hssd_viewpoint/analyze_fixed_camera_viewpoint_output.py
tools/hssd_viewpoint/inspect_hssd_semantic_mapping.py
docs/audits/hssd_category_expansion_inventory.json
```

## Stage 1: Generate Fixed-Camera Candidate Viewpoints

Run from this repo on the server.

```bash
RUN=server_render_v1_island_bbox_cap100_s160_dist090_bbox015_skipbad_v2

python tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py \
  --scene-root ../habitat-lab/data/scene_datasets/hssd-hab \
  --inventory-json docs/audits/hssd_category_expansion_inventory.json \
  --output-dir outputs/$RUN \
  --categories cabinet bed couch table bench vase fridge toilet tv sink chair seat \
  --max-scenes 0 \
  --max-objects-per-category 100 \
  --samples-per-object 160 \
  --candidate-radii 0.25 0.5 0.75 0.9 \
  --exclude-scene-ids 108736611_177263226 \
  --seed 13 \
  --gpu-device-id 0 \
  --debug-images \
  --max-debug-images 12000 \
  2>&1 | tee outputs/${RUN}.log
```

The prototype:

1. selects target instances from HSSD metadata;
2. preserves all category/source metadata for review;
3. matches each target to a Habitat-Sim rigid object;
4. samples candidate positions around the target bbox;
5. snaps candidates to the navmesh;
6. rejects tiny navmesh islands;
7. rejects snapped points inside the target bbox XZ footprint;
8. renders fixed-camera RGB and semantic observations;
9. computes sentinel target metrics;
10. writes debug images and scene checkpoints.

Small yawfix sanity run before scaling:

```bash
RUN=local_yawfix_sanity_scenes_102344022_102344328

python tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py \
  --scene-root ../habitat-lab/data/scene_datasets/hssd-hab \
  --inventory-json docs/audits/hssd_category_expansion_inventory.json \
  --output-dir outputs/$RUN \
  --categories plant potted_plant tv chair toilet bed \
  --scene-ids 102344022 102344328 \
  --max-scenes 0 \
  --max-objects-per-category 3 \
  --samples-per-object 32 \
  --candidate-radii 0.25 0.5 0.75 0.9 \
  --seed 13 \
  --gpu-device-id 0 \
  --debug-images \
  --max-debug-images 800
```

Review goal: off-axis targets should no longer be left/right mirrored, plants
should be less likely to sit on the frame edge, and the Stage 3 BEV forward cone
should agree with the rendered target direction.

Fixed-camera setting:

```text
image_width=640
image_height=480
hfov=79
camera_height=0.88
camera_pitch_deg=0
no tilt / no look-up / no look-down
```

Yaw is computed after navmesh snap. Post-yawfix code directly constructs a
yaw-only quaternion with `atan2(-view_dir.x, -view_dir.z)`; this avoids the
left/right mirror failure that pushed off-axis objects toward the frame edge.

Important candidate metrics:

| Field | Meaning |
|---|---|
| `visible_pixels` | sentinel target pixel count |
| `image_fraction` / `vis_ratio` | target pixel fraction of whole image |
| `bbox_frac` | target mask bbox area fraction |
| `distance_to_bbox` | preferred selection distance to target bbox surface |
| `distance_to_object` | diagnostic distance to approximate object center |
| `navigable_island_radius` | navmesh island quality signal |
| `snapped_inside_target_bbox_xz` | candidate is inside target bbox footprint |

## Stage 2: Select Valid Viewpoints

```bash
SEL=${RUN}_selection_final

python tools/hssd_viewpoint/select_fixed_camera_viewpoints.py \
  --input-json outputs/$RUN/hssd_fixed_camera_viewpoint_prototype.json \
  --output-dir outputs/$SEL \
  --bbox-metric max_axis \
  --connector and \
  --threshold-profile low_small \
  --low-small-categories toilet vase potted_plant \
  --min-visible-pixels 300 \
  --min-image-fraction 0.10 \
  --min-bbox-fraction 0.10 \
  --low-small-min-image-fraction 0.03 \
  --low-small-min-bbox-fraction 0.06 \
  --vase-min-image-fraction 0.02 \
  --vase-min-bbox-fraction 0.04 \
  --bbox-per-cat bed=0.10 couch=0.10 chair=0.05 tv=0.05 potted_plant=0.02 toilet=0.02 \
  --vis-per-cat bed=0.10 couch=0.10 chair=0.025 tv=0.025 potted_plant=0.005 toilet=0.01 \
  --min-fill-ratio 0.40 \
  --min-axis 0.10 \
  --max-min-axis-per-cat bed=0.92 \
  --max-distance 0.89 \
  --max-accepted-image-fraction 1.0 \
  --max-accepted-image-fraction-per-cat bed=0.56 \
  --reject-flags full_frame_sentinel_mask tiny_sentinel_mask \
  --min-viewpoints-per-object 1 \
  --top-k 8
```

Recommended post-yawfix train-quality policy:

- Visual gate is `AND`, not legacy `OR`: both visibility and bbox size must pass.
- Bbox metric is `max_axis`, which is better for elongated objects and the V3
  reshard convention.
- Per-category visibility/bbox thresholds keep chairs, TVs, plants, and toilets
  from being over-pruned while keeping large objects strict.
- `min_fill_ratio` and `min_axis` reject edge slivers and sparse masks.
- Bed gets extra close-up handling through `max_min_axis` and
  `max_accepted_image_fraction_per_cat`, because some bed bboxes include nearby
  structure or collapse into wall-panel views.
- Distance is still based on `distance_to_bbox` first. Stage 2 can synthesize
  `distance_to_bbox_estimated` from per-category half-diagonal medians when old
  Stage 1 metadata lacks bbox sizes.
- The old `selection_qtight` command is now a legacy comparison baseline, not
  the preferred train-data config.

This policy is quality-first. If a particular instance is visually poor or
taxonomically ambiguous, v1 should drop it instead of relaxing thresholds for
all objects.

## Stage 3: Build Viewpoint QA Pack

```bash
QA=outputs/${SEL}_visual_qa_pack_bev_reason

python tools/hssd_viewpoint/build_fixed_camera_visual_qa_pack.py \
  --selection-json outputs/$SEL/fixed_camera_viewpoint_selection.json \
  --path-root . \
  --output-dir $QA \
  --max-per-category-status 80 \
  --max-per-failing-object 20 \
  --max-total-images 1200
```

When Stage 1 debug images are capped, Stage 3 can now self-render missing review
PNGs:

```bash
python tools/hssd_viewpoint/build_fixed_camera_visual_qa_pack.py \
  --selection-json outputs/$SEL/fixed_camera_viewpoint_selection.json \
  --path-root . \
  --output-dir $QA \
  --prototype-json outputs/$RUN/hssd_fixed_camera_viewpoint_prototype.json \
  --scene-root ../habitat-lab/data/scene_datasets/hssd-hab \
  --scene-dataset-config ../habitat-lab/data/scene_datasets/hssd-hab/hssd-hab.scene_dataset_config.json \
  --render-missing \
  --render-gpu 0 \
  --max-per-category-status 80 \
  --max-per-failing-object 20 \
  --max-total-images 1200
```

Review outputs:

- accepted/rejected/review images grouped by category/status;
- bbox overlay images;
- BEV maps per object;
- BEV colors for rejection reasons;
- `fixed_camera_visual_qa_summary.json`.

Review criteria:

- accepted images should clearly show the target under the fixed camera;
- rejected inside-bbox and tiny-island points should disappear from accepted
  sets;
- failing objects should mostly be reasonable exclusions, not systematic bugs;
- taxonomy ambiguities should be visible from object metadata and review images.

## Current v1 Viewpoint Run

Latest production-like run:

```text
server_render_v1_island_bbox_cap100_s160_dist090_bbox015_skipbad_v2
```

Summary:

```text
objects_processed: 1190
rendered_candidates: 179335
candidates_with_visible_pixels: 122287
failed_scene_count: 0
failed_object_count: 0
candidate_error_count: 0
```

Known skipped scene:

```text
108736611_177263226
```

This scene caused a native render crash in the first large run.

## Stage 4: Export ObjectNav Episodes

Use the companion rendering repo:

```text
ObjectNavigationRendering
branch: hssd-fixedcam-workflow
```

Mini export:

```bash
cd ~/autodl-tmp/workspace/hssd/ObjectNavigationRendering_fixedcam

DATA=~/autodl-tmp/workspace/hssd/habitat-lab/data
SEL=~/autodl-tmp/workspace/hssd/habitat-lab-viewpoint/outputs/server_render_v1_island_bbox_cap100_s160_dist090_bbox015_skipbad_v2_selection_final/fixed_camera_viewpoint_selection.json
SPLIT=hssd_fixedcam_v1_mini_nearestvp

python export_fixed_camera_selection_to_hssd_episodes.py \
  --selection-json $SEL \
  --data-root $DATA \
  --split $SPLIT \
  --max-scenes 2 \
  --max-objects-per-category 2 \
  --episodes-per-object 3 \
  --max-viewpoints-per-object 32
```

Exporter behavior:

- writes accepted fixed-camera viewpoints into standard HSSD ObjectNav
  `view_points`;
- preserves fixed-camera metadata on each viewpoint;
- samples start poses whose geodesic distance to nearest accepted viewpoint is
  in `[1, 30]`;
- uses all viewpoints for geodesic distance by default
  (`top_k_viewpoints_for_geo=0`);
- rejects tiny navmesh islands and large-height-change paths.

## Stage 5: Render MP4 + Parquet

```bash
OUT=~/autodl-tmp/workspace/hssd/outputs/${SPLIT}_mp4_probe_001

CUDA_VISIBLE_DEVICES=0 python render_objnav_mp4.py \
  --dataset hssd \
  --split $SPLIT \
  --data-root $DATA \
  --output-dir $OUT \
  --image-size 256 \
  --fps 10 \
  --crf 28 \
  --worker-id 0 \
  --num-workers 1 \
  --gpu-device-id 0 \
  --episodes-per-scene -1 \
  --episode-limit 60
```

For fixed-camera goals, the renderer chooses the final target viewpoint by
nearest geodesic distance from the episode start:

```text
target_viewpoint_selection_rule = nearest_geodesic
initial_geodesic == target_viewpoint_geodesic
```

This matches official `VIEW_POINTS` semantics and avoids walking to a farther
viewpoint when a closer accepted viewpoint exists.

## Stage 6: Build MP4 Review Pack

```bash
REVIEW=~/autodl-tmp/workspace/hssd/outputs/${SPLIT}_mp4_probe_001_review_pack

python build_fixed_camera_mp4_review_pack.py \
  --render-output-dir $OUT \
  --output-dir $REVIEW \
  --max-per-category 24 \
  --make-clips \
  --clip-tail-frames 80 \
  --fps 10 \
  --print-json
```

This produces:

```text
images/<category>/*_final.jpg
clips/<category>/*_tail.mp4
contact_sheets/<category>_contact_sheet.jpg
index.html
fixed_camera_mp4_review_pack_summary.json
```

## Latest Mini Probe Status

Split:

```text
hssd_fixedcam_v1_mini_nearestvp
```

Audit result:

```text
exported episodes: 57
rendered episode rows: 54
success: 54/54
target_viewpoint_selection_rule: nearest_geodesic for all rendered rows
initial_geodesic == target_viewpoint_geodesic: yes
review final images: 54
review clips: 54
review errors: 0
```

Known edge cases:

- three bed episodes were exported but not rendered;
- three vase episodes have low raw visibility ratio but moderate bbox fraction;
- render colors look gray/white on the 4090D server and are being tuned
  separately.

These are downstream render/QA policy issues, not failures of the fixed-camera
viewpoint generation logic.

## What To Share

Jing requested code and does not need generated data. Share:

- this branch with `tools/hssd_viewpoint/*`;
- the rendering branch `hssd-fixedcam-workflow`;
- README/handoff docs.

Do not commit:

- `outputs/`;
- debug images;
- MP4s;
- parquet files;
- large checkpoint JSON files.

## Next Steps

1. Pull Jing's next push and inspect threshold, image-size, category, and docs
   changes before changing local logic.
2. Verify category handling from `hssd_obj_semantics_condensed.csv`: preserve
   raw `condensed_category` and `primary_semantic_category`, then define
   `task_category` for train/eval vocabulary.
3. Compare three train threshold candidates: current per-category yawfix profile,
   a unified profile, and a tiny-vs-regular two-profile setup.
4. Keep tilt disabled unless the real robot supports tilt.
5. Decide whether Stage 1/QA/rendering should all move to `256x256`; if yes,
   scale `min_visible_pixels` and parameterize Stage 3 `--render-missing`.
6. Run a small server-side yawfix/category/resolution sanity batch before any
   full rerun.
7. Export a small split and render MP4/Parquet probes before scaling.
8. Decide final train filters for low visibility, bbox contamination, bed
   close-ups, and `visibility_verified` before the full HPC render.
