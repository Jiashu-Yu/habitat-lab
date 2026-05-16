# HSSD Fixed-camera Viewpoint Feasibility Summary

This note summarizes the first small-scale feasibility result for generating fixed-camera, instance-level, sentinel-verified viewpoints for expanded HSSD ObjectNav categories.

The result is based on:

- broad prototype run: `outputs/hssd_fixed_camera_viewpoint_prototype/`
- broad selector run: `outputs/hssd_fixed_camera_viewpoint_selection/`
- targeted retry run: `outputs/hssd_fixed_camera_viewpoint_retry_cabinet_fridge/`
- targeted retry selector: `outputs/hssd_fixed_camera_viewpoint_retry_cabinet_fridge_selection/`
- merged selector report: `outputs/hssd_fixed_camera_viewpoint_merged_selection/`

These are server runtime outputs. Generated output files are not committed to the repo.

## Goal

The immediate research goal is to test whether HSSD can support expanded ObjectNav target categories beyond the native six classes, with viewpoints that are valid under the fixed policy/evaluation camera.

This matters because the current policy/action setup does not use `look_up`, `look_down`, or tilt sweeps. A target viewpoint should therefore be valid under the actual fixed camera, not only under an oracle pitch sweep.

## Categories Tested

The first small-scale pass tested these expanded target categories:

- `bathtub`
- `bench`
- `cabinet`
- `counter`
- `desk`
- `dishwasher`
- `dresser`
- `fridge`
- `nightstand`
- `sink`
- `stool`
- `table`
- `vase`

## Pipeline Used

1. Select target objects from HSSD scene instance metadata.
2. Resolve each scene-instance object to a Habitat-Sim rigid object handle.
3. Temporarily assign a high sentinel semantic ID to the matched rigid object.
4. Render fixed-camera RGB and semantic observations.
5. Count only sentinel semantic pixels as target visibility.
6. Save RGB, binary mask, overlay, and annotated review images.
7. Classify candidates as `accepted`, `review`, or `rejected`.
8. Merge broad and targeted retry selector outputs.

## Selector Policy

Default reject rules:

- reject `full_frame_sentinel_mask`
- reject `near_full_frame_bbox`
- reject `tiny_sentinel_mask`

Default review rule:

- mark `very_large_sentinel_mask` as review, not accepted by default

Default acceptance thresholds:

- `visible_pixels >= 1000`
- `image_fraction >= 0.005`
- `distance_to_object <= 3.0`
- `image_fraction < 0.50`
- no hard-reject mask quality flags

Object-level pass condition:

- at least `3` accepted fixed-camera viewpoints per object

## Broad Run Result

The first broad small run processed 24 sampled objects.

Broad selector summary:

- accepted candidates: `122`
- rejected candidates: `161`
- review candidates: `5`
- object status: `22 pass`, `2 fail`

The two failing objects were:

- `cabinet`, scene `102343992`, instance `27`, object name `Comet 3-door Wardrobe`
- `fridge`, scene `102343992`, instance `140`, object name `ICS3013 - LIEBHERR Fridge Freezer Integrated`

Both failures were close to passing:

- cabinet had `1` accepted + `1` review viewpoint
- fridge had `2` accepted viewpoints

This indicated a sampling issue for specific instances, not a category-level failure.

## Targeted Retry Result

The targeted retry reran only:

- scene `102343992`, instance `27`, category `cabinet`
- scene `102343992`, instance `140`, category `fridge`

Retry parameters increased candidate sampling and used radii:

- `1.25`
- `1.5`
- `1.75`
- `2.0`
- `2.25`
- `2.5`
- `3.0`

Retry selector result:

| category | objects | pass | accepted viewpoints | review viewpoints | rejected candidates |
|---|---:|---:|---:|---:|---:|
| cabinet | 1 | 1 | 7 | 2 | 39 |
| fridge | 1 | 1 | 8 | 0 | 40 |

Both targeted retry objects passed.

## Merged Result

Merged selector output:

- output directory: `outputs/hssd_fixed_camera_viewpoint_merged_selection/`
- accepted candidates: `134`
- rejected candidates: `220`
- review candidates: `6`
- object status counts: `24 pass`

Merged category summary:

| category | objects | pass | review_needed | fail | accepted viewpoints | review viewpoints |
|---|---:|---:|---:|---:|---:|---:|
| bathtub | 2 | 2 | 0 | 0 | 7 | 0 |
| bench | 2 | 2 | 0 | 0 | 15 | 0 |
| cabinet | 2 | 2 | 0 | 0 | 11 | 2 |
| counter | 2 | 2 | 0 | 0 | 10 | 0 |
| desk | 2 | 2 | 0 | 0 | 8 | 0 |
| dishwasher | 1 | 1 | 0 | 0 | 4 | 0 |
| dresser | 2 | 2 | 0 | 0 | 11 | 0 |
| fridge | 2 | 2 | 0 | 0 | 11 | 1 |
| nightstand | 2 | 2 | 0 | 0 | 7 | 0 |
| sink | 1 | 1 | 0 | 0 | 5 | 0 |
| stool | 2 | 2 | 0 | 0 | 14 | 0 |
| table | 2 | 2 | 0 | 0 | 14 | 0 |
| vase | 2 | 2 | 0 | 0 | 17 | 3 |

There were no remaining failing objects and no remaining review-needed objects.

## Interpretation

This small-scale result supports the feasibility of generating fixed-camera viewpoints for expanded HSSD ObjectNav targets.

The strongest current claim is:

> In the first sampled expanded-category test, 13 categories and 24 sampled HSSD object instances all obtained at least 3 accepted fixed-camera, instance-level, sentinel-verified viewpoints after targeted retry.

This is not yet a regenerated ObjectNav dataset. It is a feasibility artifact showing that the object metadata, rigid-object mapping, sentinel visibility, candidate filtering, and targeted retry loop can produce usable viewpoint candidates.

## What This Result Does Not Prove Yet

This result does not yet prove:

- full-HSSD category-level success rates
- canonical HSSD/Habitat benchmark comparability
- OVON/HM3D transfer performance
- final training-data quality at scale
- that selected viewpoints have been written back into Habitat ObjectNav episode shards

It also does not replace manual spot checks. Review images remain important for dark, ambiguous, close-up, or large-object cases.

## Recommended Next Step

The next stage should scale from the 24-object feasibility sample to a broader category feasibility audit.

Suggested next run design:

- keep the same 13 categories
- sample more scenes and more objects per category
- keep debug images capped
- run selector and merged reports
- measure per-category pass rate before writing any dataset shards

Example direction:

```bash
python tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py \
  --scene-root data/scene_datasets/hssd-hab \
  --inventory-json docs/audits/hssd_category_expansion_inventory.json \
  --output-dir outputs/hssd_fixed_camera_viewpoint_scale_probe \
  --categories table cabinet dresser stool fridge bathtub bench desk counter sink nightstand dishwasher vase \
  --max-scenes 10 \
  --max-objects-per-category 10 \
  --samples-per-object 48 \
  --candidate-radii 1.25 1.5 1.75 2.0 2.25 2.5 3.0 \
  --debug-images \
  --max-debug-images 800
```

Then:

```bash
python tools/hssd_viewpoint/select_fixed_camera_viewpoints.py \
  --input-json outputs/hssd_fixed_camera_viewpoint_scale_probe/hssd_fixed_camera_viewpoint_prototype.json \
  --output-dir outputs/hssd_fixed_camera_viewpoint_scale_probe_selection \
  --min-viewpoints-per-object 3
```

If the broader scale probe has high pass rates, the next engineering step is to add a writer for Habitat-compatible `view_points` records. That writer should remain separate from the audit/prototype scripts until the selection policy is stable.
